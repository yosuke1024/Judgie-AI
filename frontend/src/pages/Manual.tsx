import { useEffect, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { manualApi } from '@/api/client';
import { BookOpen } from 'lucide-react';

export default function ManualPage() {
  const { i18n, t } = useTranslation();
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');

    const lang = i18n.language.startsWith('ja') ? 'ja' : 'en';
    manualApi.getManual(lang)
      .then((res) => {
        if (active) {
          setContent(res.content);
        }
      })
      .catch((err) => {
        if (active) {
          console.error('Failed to fetch manual:', err);
          setError(lang === 'ja' ? 'マニュアルの読み込みに失敗しました。' : 'Failed to load manual.');
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [i18n.language]);

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '80vh', color: '#9ca3af' }}>
        <div style={{
          width: '40px',
          height: '40px',
          border: '4px solid rgba(255,255,255,0.1)',
          borderTop: '4px solid #3b82f6',
          borderRadius: '50%',
          animation: 'spin 1s linear infinite',
          marginBottom: '16px'
        }} />
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
        <p style={{ fontSize: '0.95rem' }}>{i18n.language.startsWith('ja') ? 'マニュアルを読み込み中...' : 'Loading manual...'}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#ef4444' }}>
        <p style={{ fontSize: '1.1rem', fontWeight: 500 }}>{error}</p>
      </div>
    );
  }

  return (
    <div className="manual-page" style={{
      padding: '40px 24px',
      maxWidth: '1000px',
      margin: '0 auto',
      color: '#e5e7eb',
      lineHeight: 1.75,
      fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
        paddingBottom: '20px',
        marginBottom: '32px'
      }}>
        <div style={{
          background: 'rgba(59, 130, 246, 0.1)',
          padding: '8px',
          borderRadius: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}>
          <BookOpen size={28} style={{ color: '#60a5fa' }} />
        </div>
        <div>
          <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 700, color: '#ffffff', letterSpacing: '-0.025em' }}>
            {t('nav.manual')}
          </h1>
          <p style={{ margin: '4px 0 0 0', fontSize: '0.875rem', color: '#9ca3af' }}>
            {i18n.language.startsWith('ja') ? 'Judgie-AI の操作方法とガイドライン' : 'Judgie-AI user guide and guidelines'}
          </p>
        </div>
      </div>

      <div className="manual-body-content" style={{ fontSize: '1rem' }}>
        {renderMarkdown(content)}
      </div>
    </div>
  );
}

function renderMarkdown(md: string): ReactNode[] {
  const lines = md.split('\n');
  const elements: ReactNode[] = [];
  let currentList: ReactNode[] = [];
  let listKey = 0;
  let inTable = false;
  let tableRows: string[][] = [];
  let inAlert = false;
  let alertType = '';
  let alertLines: string[] = [];

  const parseInline = (text: string): ReactNode[] => {
    let parts: ReactNode[] = [text];

    // 1. Inline code: `code`
    parts = parts.flatMap((part) => {
      if (typeof part !== 'string') return part;
      const codeRegex = /`([^`]+)`/g;
      const matches = [...part.matchAll(codeRegex)];
      if (matches.length === 0) return part;
      const res: ReactNode[] = [];
      let lastIndex = 0;
      for (const match of matches) {
        const index = match.index!;
        if (index > lastIndex) {
          res.push(part.substring(lastIndex, index));
        }
        res.push(
          <code key={`code-${index}`} style={{
            background: 'rgba(255, 255, 255, 0.08)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.875em',
            fontFamily: 'SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace',
            color: '#f472b6'
          }}>
            {match[1]}
          </code>
        );
        lastIndex = index + match[0].length;
      }
      if (lastIndex < part.length) {
        res.push(part.substring(lastIndex));
      }
      return res;
    });

    // 2. Bold: **text**
    parts = parts.flatMap((part) => {
      if (typeof part !== 'string') return part;
      const boldRegex = /\*\*([^*]+)\*\*/g;
      const matches = [...part.matchAll(boldRegex)];
      if (matches.length === 0) return part;
      const res: ReactNode[] = [];
      let lastIndex = 0;
      for (const match of matches) {
        const index = match.index!;
        if (index > lastIndex) {
          res.push(part.substring(lastIndex, index));
        }
        res.push(<strong key={`bold-${index}`} style={{ fontWeight: 600, color: '#ffffff' }}>{match[1]}</strong>);
        lastIndex = index + match[0].length;
      }
      if (lastIndex < part.length) {
        res.push(part.substring(lastIndex));
      }
      return res;
    });

    // 3. Links: [text](href)
    parts = parts.flatMap((part) => {
      if (typeof part !== 'string') return part;
      const linkRegex = /\[([^\]]+)\]\(([^)]+)\)/g;
      const matches = [...part.matchAll(linkRegex)];
      if (matches.length === 0) return part;
      const res: ReactNode[] = [];
      let lastIndex = 0;
      for (const match of matches) {
        const index = match.index!;
        if (index > lastIndex) {
          res.push(part.substring(lastIndex, index));
        }
        const href = match[2];
        const isAnchor = href.startsWith('#');
        res.push(
          <a
            key={`link-${index}`}
            href={isAnchor ? undefined : href}
            style={{
              color: '#3b82f6',
              textDecoration: 'none',
              fontWeight: 500,
              borderBottom: '1px solid rgba(59, 130, 246, 0.4)',
              cursor: isAnchor ? 'default' : 'pointer',
              transition: 'border-color 0.2s'
            }}
            target={isAnchor ? undefined : '_blank'}
            rel={isAnchor ? undefined : 'noopener noreferrer'}
          >
            {match[1]}
          </a>
        );
        lastIndex = index + match[0].length;
      }
      if (lastIndex < part.length) {
        res.push(part.substring(lastIndex));
      }
      return res;
    });

    return parts;
  };

  const flushList = (key: number) => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`list-${key}`} style={{
          paddingLeft: '24px',
          marginBottom: '20px',
          listStyleType: 'disc',
          display: 'flex',
          flexDirection: 'column',
          gap: '6px'
        }}>
          {currentList}
        </ul>
      );
      currentList = [];
    }
  };

  const flushTable = (key: number) => {
    if (tableRows.length > 0) {
      const isHeaderSeparator = (row: string[]) => row.every(cell => /^[:-|-]+$/.test(cell.trim()) || cell.trim() === '');
      const filteredRows = tableRows.filter(row => !isHeaderSeparator(row));

      if (filteredRows.length > 0) {
        const header = filteredRows[0];
        const body = filteredRows.slice(1);
        elements.push(
          <div key={`table-wrapper-${key}`} style={{
            overflowX: 'auto',
            marginBottom: '28px',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '8px',
            background: 'rgba(255,255,255,0.01)'
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem', textAlign: 'left' }}>
              <thead>
                <tr style={{
                  borderBottom: '1px solid rgba(255,255,255,0.1)',
                  background: 'rgba(255,255,255,0.03)'
                }}>
                  {header.map((cell, idx) => (
                    <th key={`th-${idx}`} style={{ padding: '12px 16px', fontWeight: 600, color: '#9ca3af' }}>
                      {parseInline(cell.trim())}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {body.map((row, rowIdx) => (
                  <tr key={`tr-${rowIdx}`} style={{
                    borderBottom: rowIdx < body.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
                    transition: 'background-color 0.2s',
                  }}>
                    {row.map((cell, idx) => (
                      <td key={`td-${idx}`} style={{ padding: '12px 16px', color: '#d1d5db' }}>
                        {parseInline(cell.trim())}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      tableRows = [];
    }
  };

  const flushAlert = (key: number) => {
    if (inAlert) {
      let bgColor = 'rgba(59, 130, 246, 0.05)';
      let borderColor = '#3b82f6';
      let title = 'NOTE';

      if (alertType === 'WARNING') {
        bgColor = 'rgba(245, 158, 11, 0.05)';
        borderColor = '#f59e0b';
        title = 'WARNING';
      } else if (alertType === 'CAUTION') {
        bgColor = 'rgba(239, 68, 68, 0.05)';
        borderColor = '#ef4444';
        title = 'CAUTION';
      }

      elements.push(
        <div key={`alert-${key}`} style={{
          padding: '16px 20px',
          borderRadius: '8px',
          borderLeft: `4px solid ${borderColor}`,
          background: bgColor,
          marginBottom: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}>
          <div style={{
            fontWeight: 700,
            fontSize: '0.75rem',
            letterSpacing: '0.05em',
            color: borderColor,
            textTransform: 'uppercase'
          }}>
            {title}
          </div>
          <div style={{ fontSize: '0.9rem', color: '#d1d5db', margin: 0 }}>
            {alertLines.map((line, idx) => (
              <p key={idx} style={{ margin: 0, marginBottom: idx < alertLines.length - 1 ? '8px' : 0 }}>
                {parseInline(line)}
              </p>
            ))}
          </div>
        </div>
      );
      inAlert = false;
      alertLines = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 1. Alert block handling
    if (line.startsWith('>')) {
      flushList(i);
      flushTable(i);
      const alertHeaderMatch = line.match(/^>\s*\[!(NOTE|WARNING|CAUTION)\]/i);
      if (alertHeaderMatch) {
        flushAlert(i);
        inAlert = true;
        alertType = alertHeaderMatch[1].toUpperCase();
      } else if (inAlert) {
        const contentLine = line.replace(/^>\s?/, '');
        alertLines.push(contentLine);
      }
      continue;
    } else {
      flushAlert(i);
    }

    // 2. Table handling
    if (line.trim().startsWith('|') && line.trim().endsWith('|')) {
      flushList(i);
      const cells = line.trim().split('|').slice(1, -1);
      tableRows.push(cells);
      inTable = true;
      continue;
    } else {
      if (inTable) {
        flushTable(i);
        inTable = false;
      }
    }

    // 3. Headings
    if (line.startsWith('# ')) {
      flushList(i);
      elements.push(
        <h1 key={i} style={{
          fontSize: '1.75rem',
          fontWeight: 700,
          color: '#ffffff',
          marginTop: '36px',
          marginBottom: '18px',
          letterSpacing: '-0.02em'
        }}>
          {parseInline(line.substring(2))}
        </h1>
      );
    } else if (line.startsWith('## ')) {
      flushList(i);
      elements.push(
        <h2 key={i} style={{
          fontSize: '1.375rem',
          fontWeight: 600,
          color: '#ffffff',
          marginTop: '32px',
          marginBottom: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.08)',
          paddingBottom: '8px',
          letterSpacing: '-0.015em'
        }}>
          {parseInline(line.substring(3))}
        </h2>
      );
    } else if (line.startsWith('### ')) {
      flushList(i);
      elements.push(
        <h3 key={i} style={{
          fontSize: '1.125rem',
          fontWeight: 600,
          color: '#ffffff',
          marginTop: '28px',
          marginBottom: '12px'
        }}>
          {parseInline(line.substring(4))}
        </h3>
      );
    } else if (line.startsWith('#### ')) {
      flushList(i);
      elements.push(
        <h4 key={i} style={{
          fontSize: '1rem',
          fontWeight: 600,
          color: '#ffffff',
          marginTop: '24px',
          marginBottom: '10px'
        }}>
          {parseInline(line.substring(5))}
        </h4>
      );
    }
    // 4. Horizontal Rule
    else if (line.trim() === '---') {
      flushList(i);
      elements.push(<hr key={i} style={{ border: 'none', borderTop: '1px solid rgba(255,255,255,0.08)', margin: '36px 0' }} />);
    }
    // 5. Unordered List Items
    else if (line.trim().startsWith('* ') || line.trim().startsWith('- ')) {
      const bulletContent = line.trim().substring(2);
      currentList.push(
        <li key={`li-${listKey++}`} style={{ color: '#d1d5db' }}>
          {parseInline(bulletContent)}
        </li>
      );
    }
    // 6. Empty Line
    else if (line.trim() === '') {
      flushList(i);
    }
    // 7. Regular Paragraph
    else {
      flushList(i);
      elements.push(
        <p key={i} style={{ marginBottom: '20px', color: '#d1d5db' }}>
          {parseInline(line)}
        </p>
      );
    }
  }

  // Flush remaining blocks
  flushList(lines.length);
  flushTable(lines.length);
  flushAlert(lines.length);

  return elements;
}
