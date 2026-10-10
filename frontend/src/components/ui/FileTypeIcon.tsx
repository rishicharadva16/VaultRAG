import React from 'react';
import { FileText, FileSpreadsheet, FileImage, FileCode, File } from 'lucide-react';
import { DocumentKind } from '../../api/types';

export interface FileTypeIconProps {
  kind: DocumentKind | string;
  size?: number;
  className?: string;
}

export const FileTypeIcon: React.FC<FileTypeIconProps> = ({
  kind,
  size = 18,
  className = '',
}) => {
  const norm = (kind || '').toLowerCase();

  switch (norm) {
    case 'pdf':
      return <FileText className={`text-rose-500 shrink-0 ${className}`} size={size} aria-hidden="true" />;
    case 'csv':
      return <FileSpreadsheet className={`text-emerald-600 dark:text-emerald-400 shrink-0 ${className}`} size={size} aria-hidden="true" />;
    case 'image':
    case 'png':
    case 'jpg':
    case 'jpeg':
      return <FileImage className={`text-blue-500 shrink-0 ${className}`} size={size} aria-hidden="true" />;
    case 'text':
    case 'txt':
    case 'md':
      return <FileCode className={`text-amber-500 shrink-0 ${className}`} size={size} aria-hidden="true" />;
    default:
      return <File className={`text-text-muted shrink-0 ${className}`} size={size} aria-hidden="true" />;
  }
};
