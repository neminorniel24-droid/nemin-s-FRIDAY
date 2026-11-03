// Turns written text into text that sounds right out loud. The screen keeps the nicer written version.
// Rule: she should never read out a symbol. No "slash", "asterisk", "hash", "underscore", no "e g".

const ABBREVIATIONS: [RegExp, string][] = [
  [/\be\.g\.?(?=[\s,]|$)/gi, "for example"],
  [/\bi\.e\.?(?=[\s,]|$)/gi, "that is"],
  [/\betc\b(\.?)/gi, "and so on$1"],
  [/\bvs\.?(?=\s)/gi, "versus"],
  [/\bapprox\.?(?=\s)/gi, "approximately"],
  [/\bw\/o\b/gi, "without"],
  [/\bw\/(?=\s)/gi, "with"],
  [/\bkm\/h\b/gi, "kilometres an hour"],
  [/\bmph\b/gi, "miles an hour"],
  [/\b(\d+)\s?GB\b/g, "$1 gigabytes"],
  [/\b(\d+)\s?MB\b/g, "$1 megabytes"],
  [/\b(\d+)\s?KB\b/g, "$1 kilobytes"],
  [/\bGPU\b/g, "G P U"],
  [/\bCPU\b/g, "C P U"],
];

/** Light clean for the screen: keep the words, drop the markdown marks. */
export function cleanForDisplay(input: string): string {
  return input
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s{0,3}#{1,6}\s*/gm, "")
    .replace(/(\*\*|__)(.*?)\1/g, "$2")
    .replace(/(^|[\s(])\*(\S[^*]*?)\*(?=[\s).,!?]|$)/g, "$1$2")
    .replace(/^\s*[-*•]\s+/gm, "• ")
    .replace(/[ \t]+/g, " ")
    .trim();
}

export function cleanForSpeech(input: string): string {
  let t = input;
  t = t.replace(/```[\s\S]*?```/g, " ");                       // code blocks are never read out
  t = t.replace(/`([^`]*)`/g, "$1");
  t = t.replace(/!?\[([^\]]*)\]\([^)]*\)/g, "$1");             // [text](link) -> text
  t = t.replace(/\bhttps?:\/\/(?:www\.)?([^\s/)\]]+)([^\s)\]]*)/gi, (_m, host: string, rest: string) => host + (rest.match(/[.,;:!?]+$/)?.[0] ?? "")); // a web address -> just the site name
  t = t.replace(/\b[A-Za-z]:\\(?:[^\s\\]+\\)*([^\s\\]+)/g, "$1");        // C:\a\b\file.txt -> file.txt
  t = t.replace(/(^|[\s(])((?:\/[\w.\-~@]+){2,})\/?(?=[\s,;:!?)]|$)/g, (_m, pre: string, path: string) => pre + path.split("/").pop());
  for (const [re, to] of ABBREVIATIONS) t = t.replace(re, to);

  t = t.replace(/^\s{0,3}#{1,6}\s*/gm, "");                    // headings
  t = t.replace(/^\s*>\s?/gm, "");                             // quotes
  t = t.replace(/^\s*[-*•]\s+/gm, "");                         // bullets
  t = t.replace(/^\s*\d+[.)]\s+/gm, "");                       // "1. " list numbers
  t = t.replace(/(\*\*|__)(.*?)\1/g, "$2");
  t = t.replace(/(\w)_(?=\w)/g, "$1 ");                        // snake_case -> snake case
  t = t.replace(/[*_~^]+/g, " ");
  t = t.replace(/₹\s?(\d[\d,.]*)/g, "$1 rupees");
  t = t.replace(/\$\s?(\d[\d,.]*)/g, "$1 dollars");
  t = t.replace(/(\d)\s?°\s?C\b/g, "$1 degrees Celsius").replace(/(\d)\s?°\s?F\b/g, "$1 degrees Fahrenheit").replace(/°/g, " degrees ");
  t = t.replace(/(\d)\s?%/g, "$1 percent");
  t = t.replace(/\s?(->|=>|→)\s?/g, " to ").replace(/\s?(<-|<=|←)\s?/g, " from ");
  t = t.replace(/&/g, " and ").replace(/@/g, " at ");
  t = t.replace(/(\d)\s?\+\s?(?=\d)/g, "$1 plus ").replace(/\s=\s/g, " equals ");
  t = t.replace(/~\s?(?=\d)/g, "about ");
  t = t.replace(/[|]+/g, ", ");
  t = t.replace(/[\\/]+/g, " ");                               // any slash left over
  t = t.replace(/[[\]{}<>#"“”«»]/g, " ");
  t = t.replace(/[()]/g, ", ");                                // (side note) -> , side note,
  t = t.replace(/[\u{1F000}-\u{1FAFF}\u{2190}-\u{21FF}\u{2300}-\u{23FF}\u{2600}-\u{27BF}\u{FE0F}]/gu, " "); // emoji and arrows
  t = t.replace(/\s[-–—]{1,2}\s/g, ", ");                      // spaced dashes are a pause
  t = t.replace(/…|\.{3,}/g, ".");

  t = t.replace(/\s*\n+\s*/g, (m, off: number, all: string) => (/[.!?:,;]\s*$/.test(all.slice(0, off)) ? " " : ". "));
  t = t.replace(/,\s*(,\s*)+/g, ", ").replace(/\s+,/g, ",").replace(/,\s*\./g, ".").replace(/\.\s*\./g, ".").replace(/\.,/g, ",");
  t = t.replace(/[ \t]+/g, " ").replace(/^[\s,.;:]+/, "").trim();
  return t;
}
