import Markdown from "react-markdown";

export function WikiMarkdown({ children }: { children: string }) {
  return (
    <div className="wiki-prose">
      <Markdown
        skipHtml
        disallowedElements={["img"]}
        components={{
          a: ({ href, children }) => (
            <a href={href} rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {children}
      </Markdown>
    </div>
  );
}
