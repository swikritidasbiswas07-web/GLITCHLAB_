import { useState } from 'react';

type Props = { page: string; openPage: (page: string) => void };

const questions = [
  {
    question: 'Does a passed test mean my content is legally compliant?',
    answer: 'No. A pass only means that the currently configured rules found no matching issues in that tested draft. GLITCHLAB_ is not a legal certification service, and human review remains necessary.'
  },
  {
    question: 'Will the AI automatically change or approve my content?',
    answer: 'No. Gemini analysis is opt-in and advisory. The deterministic tests and recorded human decisions remain separate. AI suggestions are not automatically published or treated as verified evidence.'
  },
  {
    question: 'Can I upload my own brand guidelines?',
    answer: 'Yes, this prototype accepts UTF-8 TXT and selectable-text PDF guidelines within its upload limits. Imported text is not automatically converted into approved rules. AI can propose candidate rules for manual review.'
  },
  {
    question: 'Why are only certain violations detected?',
    answer: 'The test runner evaluates the active configured patterns and associated rules. More nuanced problems may require additional policies, optional AI review, or an authorised human reviewer.'
  },
  {
    question: 'Is this a secure place for confidential campaign material?',
    answer: 'Not yet. This is an experimental demo without authentication or private workspaces. Use only fictional or authorised public material. See the Privacy Policy for limitations.'
  },
  {
    question: 'What happens after I apply a correction?',
    answer: 'A correction changes the editor text. When you run the tests again, the updated draft becomes a new version; the previous draft and test history are retained. Approval requires a passing test on the current version.'
  }
];

export default function InfoPages({ page, openPage }: Props) {
  const [expanded, setExpanded] = useState<number | null>(0);

  if (page === 'Home') {
    return <section className="infoPage infoHome" aria-label="About GLITCHLAB">
      <div className="infoIntro"><div className="infoPrint">GLITCHLAB_ / AXIOM</div><p className="infoStatement">A brand draft can fail for two reasons: <em>the writing is wrong, or the rules aren't clear.</em> We're building a laboratory that makes both visible.</p><button className="infoCTA" onClick={() => openPage('Content Lab')}>Open the working Content Lab <span aria-hidden="true">↗</span></button></div>
      <div className="infoEditorial"><div className="infoEditorialSide">WHAT'S REAL IN THIS DEMO</div><div><h2>Evidence before approval.</h2><p>GLITCHLAB_ checks drafts against active brand rules, shows matched text and source labels, suggests small edits, and keeps a revision trail. The final decision is recorded by a human reviewer.</p><p>It also supports PDF/TXT guideline uploads and optional Gemini-assisted analysis. AI output is advisory, never an automatic approval.</p><button className="infoTextLink" onClick={() => openPage('Features')}>See the current feature set ↗</button></div></div>
    </section>;
  }

  if (page === 'Features') {
    return <section className="infoPage" aria-label="GLITCHLAB features">
      <div className="infoFeature"><span className="infoFeatureTag">CONTENT LAB</span><div><h2>Find the exact fault.</h2><p>Submit a text draft, apply active terminology, factual-pattern and promotional-claim tests, and inspect each finding alongside its matched text and rule source.</p></div></div>
      <div className="infoFeature"><span className="infoFeatureTag">KNOWLEDGE VAULT</span><div><h2>Keep the rules in view.</h2><p>Add active rules manually; import UTF-8 TXT or text-based PDF guidance. Imported files do not silently become approved policy.</p></div></div>
      <div className="infoFeature"><span className="infoFeatureTag">PATCH + RETEST</span><div><h2>Fix less. Verify more.</h2><p>Apply proposed small edits, run the checks again, and preserve draft versions instead of erasing earlier work.</p></div></div>
      <div className="infoFeature"><span className="infoFeatureTag">HUMAN GATE</span><div><h2>A person makes the call.</h2><p>Record comments, requests for changes, and approval decisions. A draft with unresolved configured-rule failures cannot be approved in the demo workflow.</p></div></div>
      <div className="infoFeature"><span className="infoFeatureTag">OPTIONAL AI</span><div><h2>Interpretation, not authority.</h2><p>Gemini can provide contextual brand observations and propose rules from source text when explicitly requested. Its output needs human verification.</p></div></div>
      <div className="infoCaution"><strong>Prototype limitations</strong><p>Current checks are not exhaustive fact verification, legal compliance certification, or a substitute for accessibility and security audits. The shared demo does not authenticate reviewers.</p></div>
    </section>;
  }

  if (page === 'How it works') {
    return <section className="infoPage" aria-label="How GLITCHLAB works">
      <div className="infoRoute"><div className="infoRouteLead">An actual workflow.<span>Not a slide deck.</span></div>
        {[
          ['Bring your rules', 'Use the seeded NovaCell X policies, add your own rule, or import a TXT/PDF document. A human controls which rules are active.'],
          ['Submit a draft', 'Enter marketing copy in Content Lab, choose a channel, and save or run tests.'],
          ['Inspect the evidence', 'See each failed pattern, the affected phrase, the source label and a suggested alternative. Optional AI can provide additional advisory analysis.'],
          ['Patch and retest', 'Apply an edit, create a new draft version and rerun the configured checks. Earlier versions stay in the audit trail.'],
          ['Make the decision', 'Use Review Station to request changes or approve a passing tested version. Review decisions remain visible in history.']
        ].map(([name, description], index) => <div className="infoRouteStep" key={name}><span>{String(index + 1).padStart(2, '0')}</span><div><h2>{name}</h2><p>{description}</p></div></div>)}
      </div><button className="infoCTA" onClick={() => openPage('Content Lab')}>Try it with the NovaCell sample ↗</button>
    </section>;
  }

  return <section className="infoPage" aria-label="Frequently asked questions">
    <div className="infoFAQIntro">Six questions worth answering before anyone trusts a content-testing tool.</div>
    <div className="infoFAQList">{questions.map((item, index) => <div className="infoFAQItem" key={item.question}>
      <button type="button" className="infoFAQQuestion" aria-expanded={expanded === index} onClick={() => setExpanded(expanded === index ? null : index)}><span>{item.question}</span><b aria-hidden="true">{expanded === index ? '−' : '+'}</b></button>
      {expanded === index && <p>{item.answer}</p>}
    </div>)}</div>
    <button className="infoTextLink" onClick={() => openPage('Privacy Policy')}>Read the Privacy Policy ↗</button>
  </section>;
}
