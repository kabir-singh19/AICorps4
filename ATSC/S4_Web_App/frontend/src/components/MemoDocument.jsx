import React from 'react';

// Renders the S3 memo Markdown (headings, paragraphs, bullet and numbered lists, pipe tables,
// bare URLs) as React elements. No HTML from the memo is injected, so nothing in it can run.

const URL = /(https?:\/\/[^\s)]+)/g;
const LABEL = /^([A-Z][A-Za-z /&+-]{1,40}|CM\d{3}):\s/;

function inline(text) {
  const out = [];
  let last = 0;
  for (const m of text.matchAll(URL)) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const url = m[0].replace(/[.,;]+$/, '');
    const host = url.replace(/^https?:\/\//, '').split('/')[0];
    const id = url.match(/facid=(\d+)/);
    out.push(<a key={m.index} href={url} target="_blank" rel="noopener noreferrer">{id ? 'view record ↗' : `${host} ↗`}</a>);
    out.push(m[0].slice(url.length));
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function labelled(text) {
  const m = text.match(LABEL);
  return m ? <><strong>{m[1]}:</strong> {inline(text.slice(m[0].length))}</> : inline(text);
}

function parse(md) {
  const lines = md.replace(/\r/g, '').split('\n');
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) { blocks.push({ type: `h${h[1].length}`, text: h[2] }); i++; continue; }
    if (line.startsWith('|')) {
      const rows = [];
      while (i < lines.length && lines[i].startsWith('|')) {
        if (!/^\|[\s:|-]+\|?$/.test(lines[i])) rows.push(lines[i].replace(/^\||\|$/g, '').split('|').map(c => c.trim()));
        i++;
      }
      blocks.push({ type: 'table', rows });
      continue;
    }
    const list = line.match(/^(-|\d+\.)\s+/);
    if (list) {
      const ordered = list[1] !== '-';
      const items = [];
      while (i < lines.length && (ordered ? /^\d+\.\s+/ : /^-\s+/).test(lines[i])) {
        items.push(lines[i].replace(/^(-|\d+\.)\s+/, ''));
        i++;
      }
      blocks.push({ type: ordered ? 'ol' : 'ul', items });
      continue;
    }
    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3}\s|\||-\s|\d+\.\s)/.test(lines[i])) para.push(lines[i++]);
    blocks.push({ type: 'p', text: para.join(' ') });
  }
  return blocks;
}

function factor(text) {
  const m = text.match(/^(.*)\((raises|lowers) risk\)\s*$/);
  if (!m) return labelled(text);
  return <><span className={`pill ${m[2] === 'raises' ? 'pill-up' : 'pill-down'}`}>{m[2] === 'raises' ? '▲ raises risk' : '▼ lowers risk'}</span> {m[1].trim()}</>;
}

function Block({ b, first }) {
  switch (b.type) {
    case 'h2': return <h2>{b.text}</h2>;
    case 'h3': return null; // rendered as a countermeasure card heading
    case 'p': return first ? <p className="memo-banner">{inline(b.text)}</p> : <p>{inline(b.text)}</p>;
    case 'ul': return <ul>{b.items.map((t, k) => <li key={k}>{labelled(t)}</li>)}</ul>;
    case 'ol': return <ol className="memo-factors">{b.items.map((t, k) => <li key={k}>{factor(t)}</li>)}</ol>;
    case 'table': {
      const [head, ...body] = b.rows;
      return <div className="table-scroll"><table className="memo-table"><thead><tr>{head.map((c, k) => <th key={k} scope="col">{c}</th>)}</tr></thead>
        <tbody>{body.map((r, k) => <tr key={k}>{r.map((c, j) => j === 0 ? <th key={j} scope="row">{c}</th> : <td key={j}>{c}</td>)}</tr>)}</tbody></table></div>;
    }
    default: return null;
  }
}

export default function MemoDocument({ markdown }) {
  const blocks = parse(markdown);
  const title = blocks.find(b => b.type === 'h1');
  // Group the blocks that follow each ### heading into one countermeasure card.
  const out = [];
  let card = null;
  let firstPara = true;
  blocks.forEach((b, k) => {
    if (b.type === 'h1') return;
    if (b.type === 'h3') { card = { key: k, title: b.text, blocks: [] }; out.push(card); return; }
    if (b.type === 'h2') card = null;
    const el = <Block key={k} b={b} first={b.type === 'p' && firstPara} />;
    if (b.type === 'p') firstPara = false;
    if (card) card.blocks.push(el); else out.push(el);
  });
  return <article className="memo-doc">
    {title && <h1 className="memo-title">{title.text}</h1>}
    {out.map(x => x?.blocks ? <section key={x.key} className="cm-card"><h3>{x.title}</h3>{x.blocks}</section> : x)}
  </article>;
}
