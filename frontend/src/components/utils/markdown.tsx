import { Anchor, Typography } from '@mantine/core';
import ReactMarkdown, { defaultUrlTransform } from 'react-markdown';
import remarkGfm from 'remark-gfm';

const SAFE_LINK = /^(https?:|mailto:|#)/i;

/**
 * Shows text written by an organiser as Markdown (headings, lists, bold, links, tables).
 *
 * Safe for public pages: raw HTML in the text is not rendered (react-markdown drops it unless a
 * plugin like rehype-raw is added, which we don't), images are not loaded, and links are limited
 * to http(s) and mailto and open in a new tab without access to this page.
 */
export function MarkdownView({ text }: { text: string }) {
  return (
    <Typography>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        disallowedElements={['img']}
        unwrapDisallowed
        urlTransform={(url) => {
          const safe = defaultUrlTransform(url);
          return SAFE_LINK.test(safe) ? safe : '';
        }}
        components={{
          a: ({ href, children }) =>
            href ? (
              <Anchor href={href} target="_blank" rel="noopener noreferrer">
                {children}
              </Anchor>
            ) : (
              <>{children}</>
            ),
        }}
      >
        {text}
      </ReactMarkdown>
    </Typography>
  );
}

/** Markdown reduced to plain text, e.g. for pasting into a form that doesn't support it. */
export function markdownToPlainText(text: string): string {
  return text
    .replace(/<[^>]*>/g, '') // HTML tags (not shown on the rules page either)
    .replace(/^#{1,6}\s+/gm, '') // headings
    .replace(/\*\*(.+?)\*\*|__(.+?)__/g, '$1$2') // bold
    .replace(/(^|[^*\w])\*(?!\s)(.+?)\*(?!\w)/g, '$1$2') // italic
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)') // links: keep the address
    .replace(/^(\s*)[*+]\s+/gm, '$1- ') // bullets as "-"
    .replace(/^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$/gm, '') // table separator rows
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}
