/* Landing page copy, in one place so it can be rewritten without touching
 * layout code. The hero line is the thing most likely to change. */

export const HERO = {
  /* "Agent Harness" rather than "Coding Agent", because the subject of the
     site is the harness: the machinery around a model that every agent
     needs, whatever it is pointed at. Code is the specimen, not the scope.

     The accent line carries that qualification, so the promise and its
     boundary arrive together rather than the boundary arriving later. */
  title: "Build Your Very-First Agent Harness",
  titleAccent: "Starting from Coding Agent",

  /* Two lines, the second carrying the emphasis: the point of the course is
     that you type the code.

     The opener quotes "harness" because it is being used as a verb the
     reader may not have met yet, and the quotes mark it as the term the
     site is about rather than a typo. Curly quotes: this renders through
     esc(), so the characters go in directly. */
  taglineOpener: "Learning to “harness” is the new paradigm of learning to code.",
  taglineLead: "Here is all the core info you need to understand how harness works.",
  taglineEmphasis: "Prepare to get your hands dirty by",
  taglineStress: "writing real code",

  /* One sentence, and it is the one a visitor needs before pressing the
     button: can I actually do this?

     The author's background used to sit here and now opens ABOUT further
     down the page, where a reader who wants to know who wrote this will
     look for it. The hero's job is the offer, not the biography. */
  lede: ["Basic Python knowledge is enough to start the course."],
  // The lede used to close on "Let's get started." one line above a button
  // reading "Start to Build!" - the same beat twice. The button says it now.
  ledeClose: "",

  cta: "Let's get started",
  ctaSub: "No signup. Nothing to install. Runs in this tab.",
};

/* The curriculum heading. The subhead is a function because the counts come
   from the loaded bundle rather than from this file - they drifted twice
   when they were written by hand.

   "Track one" is the only forward-looking claim on the page, and ROADMAP
   below says plainly that the rest is unwritten. The distinction matters:
   the architecture here is genuinely general, but the levels are all coding
   agents, and the page should not blur the two. */
export const CURRICULUM_TITLE = "The curriculum";

export const curriculumSub = (acts, levels) =>
  `Track one: coding agents. ${acts} acts, ${levels} levels. ` +
  "Each one opens with a question, not a definition.";

/* Shown under the level list. Named tracks rather than a vague "more to
   come", because each one says what it would actually build. Still labelled
   "Coming soon", so nobody reads them as shipped: all sixteen levels today
   are coding agents.

   Three now, which is why the grid is three columns at desktop width. */
export const ROADMAP_TITLE = "Coming soon";

export const ROADMAP_TRACKS = [
  { name: "Research Harness", body: "How to build a research agent." },
  { name: "Personal Harness", body: "How to build a personal agent." },
  { name: "Fleet Harness", body: "How to lead your agent fleet." },
];

/* The follow-up, directly under the roadmap: the tracks above are the one
   thing on the page a reader might want to be told about later, so the
   invitation belongs here rather than in the footer.

   URLs taken from the profile links on schen.app, not guessed. */
export const ROADMAP_FOLLOW = {
  before: "Follow me on",
  after: "to get updated.",
  links: [
    { label: "X", url: "https://x.com/schenapp" },
    { label: "LinkedIn", url: "https://www.linkedin.com/in/schenapp/" },
  ],
};

/* One sentence each. These are scanned, not read - the longer versions were
   accurate and ignored.

   Four now. The fourth was a standalone "Studied from a real harness" panel
   lower down the page, which was making the same kind of claim as these
   three - here is what you get - but in its own box, separated from them by
   two other sections. It is the only one with a link, so `link` is optional
   on the shape rather than required. */
export const PILLARS = [
  {
    icon: "python",
    title: "A real Python environment",
    body: "CPython runs in your browser. Your code is executed, not pattern-matched.",
  },
  {
    icon: "tutor",
    title: "A free AI tutor that is ready to support",
    body:
      "It reads your code and asks what you expect to happen. One click to " +
      "connect a free model.",
  },
  {
    icon: "feedback",
    title: "Direct feedback on the code you write",
    body:
      "When you are wrong, something concrete breaks and tells you which " +
      "invariant you violated.",
  },
  {
    icon: "specimen",
    title: "Studied from a real harness",
    body:
      "The specimen is tau, Hugging Face's Python coding agent - written to " +
      "be read, with design notes recording what broke first.",
    link: { label: "huggingface/tau", url: "https://github.com/huggingface/tau" },
  },
];

/* The visitor's real question is "what will I be able to do after this?"
   Answered with things that are true at the end of a specific level, not
   with dispositions - "explain why an abstraction exists" is not something
   anyone can picture themselves doing. */
export const OUTCOMES_TITLE = "After the course you can";

export const OUTCOMES = [
  "Build a working coding agent from an empty file, on a real model",
  "Keep a session alive after it outgrows the model's context window",
  "Decide what an agent may do on its own, and what needs a human",
  "Survive a failed request, an interrupted run, and a crash mid-write",
  "Add new tools and prompts to an agent without forking it",
  "Read any agent codebase and tell its forced parts from its choices",
];

/* "About me" occupies what used to be the standalone philosophy panel.
   The two were saying one thing in two places: the bio explained who is
   speaking, the Feynman quote explained why the course is built out of
   exercises rather than explanations. Together the claim is "here is my
   experience, and here is the method it taught me".

   Compressed to two short paragraphs. The long version argued the case for
   building over reading across five sentences, which is the kind of thing a
   reader skims - and skimming an argument about why the course works is the
   same as not making it.

   The quote closes the section on one line rather than standing in its own
   column. It reads as the conclusion of the paragraph above it, which is
   what it actually is.

   The second paragraph's metaphor is chosen to survive being taken
   seriously. The obvious one - you fly without knowing how a plane works -
   argues the wrong way: a passenger genuinely does not need to know, so the
   honest conclusion is "don't bother". Driving concedes that same point up
   front (most people never learn what a camshaft does, and nothing goes
   wrong) and then moves the reader across the line: they are not using an
   agent, they are building one, which is the mechanic's job rather than the
   driver's.

   The section itself now sits at the bottom of the page, after the roadmap,
   rendered by renderLandingFooter. "Who wrote this" is a question a reader
   has after deciding the course is worth their time. */
export const ABOUT = {
  title: "About me",
  /* Served from the site's own public/ rather than hotlinked from
     schen.app: a hotlink breaks offline, leaks a referrer on every page
     view, and ties this page to another site's asset paths. Cropped square
     and resized to 320px (24KB) from the 1364px original. */
  photo: "author.jpg",
  photoAlt: "Shuo Chen",
  homepage: "https://schen.app",
  homepageLabel: "schen.app",
  body: [
    "I built, used and conducted research on agent harness at Microsoft, " +
      "Amazon, Siemens and LMU Munich. I compiled this free course to help " +
      "those who want to learn harness.",
    "An LLM will write you an agent loop in seconds. Most people drive " +
      "without knowing what a camshaft does, and nothing goes wrong - but " +
      "nobody wants a mechanic who only knows how to drive. Building agents " +
      "puts you on the mechanic's side of that line, so this course is " +
      "sixteen things you build.",
  ],
  quote: "What I cannot create, I do not understand.",
  attribution: "Richard Feynman",
};

/* Institutions the author and early readers come from. Named because the
   course is a specific person's work, not an anonymous product. */
export const TRUSTED_LABEL = "Trusted by people from";

/* Off by default. "Trusted by" plus a row of large wordmarks is the visual
   grammar of a customer logo wall, and that is what a reader takes from it
   regardless of the literal wording - which is the kind of impression that
   invites a brand-protection notice, or in Germany a UWG competition-law
   warning. It is also a claim nobody can check: no reader can say which
   person from which organisation is meant.

   The data and the renderer are kept so the band can come back, but it needs
   two changes first: a factual label ("Early readers work and study at"), and
   a visual treatment that is not a marquee of oversized names. The author's
   own history at these organisations already sits in ABOUT, which is the
   stronger claim anyway - it is checkable and attached to a named person. */
export const SHOW_TRUSTED = false;

/* Rendered as wordmarks rather than fetched logos: real brand assets carry
   licence terms, and a row of hotlinked PNGs would break offline and leak
   referrers. These are set in the site's own type, which also keeps the band
   visually coherent.

   `mark` used to select a typeface - serif for universities, sans for
   companies. The band is set in one face now; the field is kept because it
   is the only thing distinguishing the two groups if they ever need to be
   treated differently again. */
export const TRUSTED_BY = [
  { name: "Oxford", mark: "serif" },
  { name: "Cambridge", mark: "serif" },
  { name: "LMU Munich", mark: "serif" },
  { name: "TUM", mark: "serif" },
  { name: "Google DeepMind", mark: "sans" },
  { name: "Microsoft", mark: "sans" },
  { name: "Amazon", mark: "sans" },
  { name: "Meta", mark: "sans" },
  { name: "Siemens", mark: "sans" },
];

export const SITE = {
  author: "schen.app",
  authorUrl: "https://schen.app",
  brand: "Harness Academy",
  year: new Date().getFullYear(),
};
