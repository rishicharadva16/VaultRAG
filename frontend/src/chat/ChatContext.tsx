import React, { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react';
import { api, ApiClientError } from '../api/client';
import { CitationItem } from '../api/types';
import { ChatMessage } from '../components/MessageList';
import { useAuth } from '../auth/AuthContext';

const TIMEOUT_SECONDS = 130;

export interface SourceFilter {
  source_ids: string[];
  filename: string;
}

export interface ChatContextType {
  messages: ChatMessage[];
  hasActiveConversation: boolean;
  selectedCitation: CitationItem | null;
  setSelectedCitation: (citation: CitationItem | null) => void;
  inputQuestion: string;
  setInputQuestion: (val: string) => void;
  isLoading: boolean;
  elapsedSeconds: number;
  errorMessage: string | null;
  setErrorMessage: (msg: string | null) => void;
  lastQuestion: string;
  sourceFilter: SourceFilter | null;
  setSourceFilter: (filter: SourceFilter | null) => void;
  handleSendQuestion: (question: string) => Promise<void>;
  handleStop: () => void;
  handleRetry: () => void;
  handleNewChat: () => void;
}

const defaultChatContext: ChatContextType = {
  messages: [],
  hasActiveConversation: false,
  selectedCitation: null,
  setSelectedCitation: () => {},
  inputQuestion: '',
  setInputQuestion: () => {},
  isLoading: false,
  elapsedSeconds: 0,
  errorMessage: null,
  setErrorMessage: () => {},
  lastQuestion: '',
  sourceFilter: null,
  setSourceFilter: () => {},
  handleSendQuestion: async () => {},
  handleStop: () => {},
  handleRetry: () => {},
  handleNewChat: () => {},
};

const ChatContext = createContext<ChatContextType>(defaultChatContext);

export const ChatProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>('');
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const timerIntervalRef = useRef<number | null>(null);
  const timeoutIdRef = useRef<number | null>(null);
  const prevUserIdRef = useRef<string | null>(null);

  const clearTimers = useCallback(() => {
    if (timerIntervalRef.current !== null) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (timeoutIdRef.current !== null) {
      clearTimeout(timeoutIdRef.current);
      timeoutIdRef.current = null;
    }
  }, []);

  const handleStop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    clearTimers();
    setIsLoading(false);
    // Remove the loading message if aborted
    setMessages((prev) => prev.filter((m) => !m.isLoading));
  }, [clearTimers]);

  const handleNewChat = useCallback(() => {
    handleStop();
    setMessages([]);
    setSelectedCitation(null);
    setErrorMessage(null);
    setInputQuestion('');
    setLastQuestion('');
    setSourceFilter(null);
  }, [handleStop]);

  // Reset conversation ONLY when user signs out or a different user signs in
  useEffect(() => {
    const currentUserId = user?.id ?? null;
    if (prevUserIdRef.current !== null && prevUserIdRef.current !== currentUserId) {
      handleNewChat();
    } else if (!user && messages.length > 0) {
      handleNewChat();
    }
    prevUserIdRef.current = currentUserId;
  }, [user, handleNewChat, messages.length]);

  const handleSendQuestion = async (questionToSend: string) => {
    const q = questionToSend.trim();
    if (!q || isLoading) return;

    setInputQuestion('');
    setErrorMessage(null);
    setLastQuestion(q);
    setIsLoading(true);
    setElapsedSeconds(0);

    const messageId = `msg-${Date.now()}`;
    const loadingMessage: ChatMessage = {
      id: messageId,
      question: q,
      isLoading: true,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, loadingMessage]);

    // Setup elapsed timer
    const startTime = Date.now();
    timerIntervalRef.current = window.setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);

    // Setup 130s abort timeout
    const controller = new AbortController();
    abortControllerRef.current = controller;

    timeoutIdRef.current = window.setTimeout(() => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      clearTimers();
      setIsLoading(false);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));
      setErrorMessage('The AI service took too long. Please try again.');
    }, TIMEOUT_SECONDS * 1000);

    try {
      const response = await api.ask(
        {
          question: q,
          top_k: 5,
          source_ids: sourceFilter ? sourceFilter.source_ids : undefined,
        },
        controller.signal
      );
      const latencyMs = Date.now() - startTime;

      clearTimers();
      setIsLoading(false);

      setMessages((prev) =>
        prev.map((m) =>
          m.id === messageId
            ? {
                ...m,
                isLoading: false,
                response,
                latencyMs,
              }
            : m
        )
      );
    } catch (err: unknown) {
      clearTimers();
      setIsLoading(false);
      setMessages((prev) => prev.filter((m) => m.id !== messageId));

      if (err instanceof DOMException && err.name === 'AbortError') {
        // Handled by stop/timeout
        return;
      }

      if (err instanceof ApiClientError) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage('Cannot reach the VaultRAG server. Is the backend running?');
      }
    }
  };

  const handleRetry = () => {
    if (lastQuestion) {
      handleSendQuestion(lastQuestion);
    }
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        hasActiveConversation: messages.length > 0,
        selectedCitation,
        setSelectedCitation,
        inputQuestion,
        setInputQuestion,
        isLoading,
        elapsedSeconds,
        errorMessage,
        setErrorMessage,
        lastQuestion,
        sourceFilter,
        setSourceFilter,
        handleSendQuestion,
        handleStop,
        handleRetry,
        handleNewChat,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => useContext(ChatContext);
