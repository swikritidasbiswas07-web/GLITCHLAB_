/** GLITCHLAB_ advisory overlap check. This never approves, rejects or deletes rules. */
export type ComparableRule = {
  code?: string;
  category: string;
  title: string;
  explanation: string;
  pattern: string;
  replacement?: string;
};
export type RuleOverlap = {
  rule: ComparableRule;
  reason: string;
  score: number;
};
const STOP_WORDS = new Set([
  'a','an','the','and','or','to','of','for','in','on','at','by','with','as','is','are','be','do',
  'not','use','using','without','should','must','approved','proposed','claim','claims','rule',
  'brand','product','official','from','that','this','such','than','up','only','our','their',
  'avoid','prohibit','restricted','restrict','require','requires','specified','specification'
]);
const IMPORTANT = /^(?:\d+(?:\.\d+)?|battery|novacell|guarantee|guaranteed|revolutionary|amazing|india|hour|hours|cell)$/;
function tokens(input: string): Set<string> {
  const normal = input.toLowerCase().replace(/([a-z])(\d)/g, '$1 $2').replace(/(\d)([a-z])/g, '$1 $2');
  return new Set((normal.match(/[a-z]+|\d+(?:\.\d+)?/g) || [])
    .map(w => w === 'hours' ? 'hour' : w === 'claims' ? 'claim' : w)
    .filter(w => !STOP_WORDS.has(w) && (w.length >= 3 || /^\d/.test(w))));
}
function patternKey(p: string): string {
  return p.toLowerCase().replace(/\(\?i\)/g, '').replace(/\\b/g, '')
    .replace(/\\s\+|\\s\*|\[\s\S\]/g, ' ').replace(/[^a-z0-9]+/g, ' ').trim();
}
/** Conservative, user-facing warning only. Semantic equivalence still needs human review. */
export function findPotentialOverlaps(candidate: ComparableRule, existing: ComparableRule[]): RuleOverlap[] {
  const ct = tokens(`${candidate.title} ${candidate.explanation}`);
  const matches: RuleOverlap[] = [];
  for (const rule of existing) {
    if (rule.code && candidate.code && rule.code === candidate.code) {
      matches.push({rule, reason:'The rule code is already in use.', score:1});
      continue;
    }
    const sameCategory = rule.category.toLowerCase() === candidate.category.toLowerCase();
    const cp = patternKey(candidate.pattern);
    const rp = patternKey(rule.pattern);
    if (cp && rp && cp === rp) {
      matches.push({rule, reason:'Both rules use the same matching pattern.', score:1});
      continue;
    }
    const rt = tokens(`${rule.title} ${rule.explanation}`);
    const shared = [...ct].filter(t => rt.has(t));
    const union = new Set([...ct,...rt]);
    const jaccard = union.size ? shared.length / union.size : 0;
    const coverage = Math.min(ct.size, rt.size) ? shared.length / Math.min(ct.size, rt.size) : 0;
    const specific = shared.some(t => IMPORTANT.test(t));
    const sameNumbers = shared.filter(t => /^\d/.test(t)).length >= 1;
    const sameSubject = shared.some(t => ['battery','novacell','guaranteed','india'].includes(t));
    const strongCrossCategory = !sameCategory && sameNumbers && sameSubject && shared.length >= 3 && coverage >= .48;
    if (specific && shared.length >= 3 && ((sameCategory && (jaccard >= .30 || coverage >= .57)) || strongCrossCategory)) {
      matches.push({rule, reason:`Both rules discuss ${shared.slice(0,4).join(', ')}. Their scope may overlap; inspect both before creating another rule.`, score:Math.min(.95, Math.max(jaccard, coverage))});
    }
  }
  return matches.sort((a,b)=>b.score-a.score).slice(0,3);
}
