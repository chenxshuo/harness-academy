/* The landing page.
 *
 * It used to be a curriculum dump: a headline and then twelve cards. A
 * visitor's first question is not "which level is third" - it is "what is
 * this, what will I be able to do, and why should I believe it works?"
 *
 * So: hero, the course in one diagram, what makes it different, what you
 * will be able to do, who wrote it and why. The curriculum follows
 * underneath for anyone still reading.
 */

import { esc } from "./markdown.js";
/* Inlined, not linked. The banner animates, and declarative animation does
   not run inside a CSS background-image or an <img> - browsers render both
   in secure static mode. `?raw` hands us the markup to put in the DOM,
   where the page's own stylesheet can drive it. */
import heroArt from "./hero-background.svg?raw";
import {
  ABOUT,
  HERO,
  OUTCOMES,
  OUTCOMES_TITLE,
  PILLARS,
  ROADMAP_FOLLOW,
  ROADMAP_TITLE,
  ROADMAP_TRACKS,
  SHOW_TRUSTED,
  SITE,
  TRUSTED_BY,
  TRUSTED_LABEL,
} from "./content/landing.js";

/* Line icons, 24x24, stroked not filled.
 *
 * `python` is deliberately NOT the Python logo. The two interlocking snakes
 * need their counter-shapes and two colours to be recognisable; reduced to a
 * single-colour 20px stroke outline it read as a scribble. This is a
 * terminal prompt instead, which says "real interpreter" - the actual claim
 * of that pillar - and is legible at the size it is drawn. */
const ICONS = {
  python: `<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M7 10l2.5 2L7 14"/><path d="M12.5 14.5H17"/>`,
  tutor: `<path d="M12 3 3 7.5 12 12l9-4.5L12 3Z"/><path d="M6 10v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/><path d="M21 7.5V14"/>`,
  feedback: `<path d="M9 11.5 11.5 14 16 9"/><circle cx="12" cy="12" r="9"/>`,
  // A specimen on a slide: the course reads one real harness closely.
  specimen: `<path d="M5 3.5h11l3 3V20a.5.5 0 0 1-.5.5h-13A.5.5 0 0 1 5 20V4a.5.5 0 0 1 .5-.5Z"/><path d="M15.5 3.5V7h3.5"/><path d="M8.5 12h7"/><path d="M8.5 15.5h4.5"/>`,
};

function icon(name) {
  return `<svg viewBox="0 0 24 24" width="20" height="20" fill="none"
    stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
    stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}

/* Resolve against the deployed base. Vite's `base` is "./" so the site can
   be served from a subdirectory, which means a bare "/author.jpg" would
   break there. main.js exports the same one-liner, but importing it here
   would make landing.js and main.js a cycle - main.js already imports
   this module. */
function assetUrl(path) {
  return new URL(path, document.baseURI).href;
}

/**
 * Render the landing page.
 *
 * The course-map diagram is no longer rendered here. It summarises the four
 * acts, so it now sits directly above the level list it describes, under the
 * curriculum heading - see `renderCurriculumDiagram`. Above the pitch it was
 * the first thing a visitor read, which asked them to parse the structure of
 * a course before they knew what the course was.
 */
export function renderLanding(host, { onStart, startLabel, resumeNote }) {
  host.innerHTML = `
    <header class="hero">
      <div class="hero-art" aria-hidden="true">${heroArt}</div>
      <h1>
        <span class="hero-line">${esc(HERO.title)}</span>
        <span class="hero-line hero-accent">${esc(HERO.titleAccent)}</span>
      </h1>
      <p class="hero-tagline">
        <span class="tagline-line tagline-opener">${esc(HERO.taglineOpener)}</span>
        <span class="tagline-line">${esc(HERO.taglineLead)}</span>
        <span class="tagline-line">${esc(HERO.taglineEmphasis)}
          <strong class="tagline-stress">${esc(HERO.taglineStress)}</strong>.</span>
      </p>
      <div class="hero-lede">
        ${HERO.lede.map((p) => `<p>${esc(p)}</p>`).join("")}
        ${HERO.ledeClose ? `<p class="lede-close">${esc(HERO.ledeClose)}</p>` : ""}
      </div>
      <div class="hero-actions">
        <button class="primary large" data-start>${esc(startLabel || HERO.cta)}</button>
        <span class="hero-note" id="hero-note">${esc(resumeNote || HERO.ctaSub)}</span>
      </div>
    </header>

    <section class="pillars">
      ${PILLARS.map(
        (p) => `
        <article class="pillar">
          <div class="pillar-icon">${icon(p.icon)}</div>
          <h3>${esc(p.title)}</h3>
          <p>${esc(p.body)}</p>
          ${
            p.link
              ? `<a class="pillar-link" href="${p.link.url}" target="_blank"
                    rel="noopener noreferrer">${esc(p.link.label)} &#8599;</a>`
              : ""
          }
        </article>`
      ).join("")}
    </section>

    <section class="outcomes">
      <h2>${esc(OUTCOMES_TITLE)}</h2>
      <ul>
        ${OUTCOMES.map(
          (o) => `<li><span class="tick">&#10003;</span>${esc(o)}</li>`
        ).join("")}
      </ul>
    </section>`;

  host.querySelector("[data-start]").onclick = onStart;
}

/** Update just the CTA, so progress changes do not re-render the page. */
export function updateLandingCta(host, { label, note }) {
  const button = host.querySelector("[data-start]");
  const hint = host.querySelector("#hero-note");
  if (button) button.textContent = label;
  if (hint) hint.textContent = note;
}

/**
 * The four-act overview, placed under the curriculum heading.
 *
 * Separate from `renderLanding` because its host lives outside the landing
 * container, between the heading and the act list in index.html.
 */
export function renderCurriculumDiagram(host, diagram) {
  if (host) host.innerHTML = diagram || "";
}

/**
 * The sections that belong *after* the curriculum: the roadmap, then About
 * me, then the footer.
 *
 * About me sits here rather than up in the pitch because it answers "who is
 * this person" - a question a reader has after deciding the course looks
 * worth their time, not before. Directly after the roadmap it also lands
 * next to the invitation to follow the author, which is the same subject.
 *
 * The trust band is behind SHOW_TRUSTED, currently off. See the note in
 * content/landing.js for why, and for what it would need to come back.
 */
export function renderLandingFooter(host) {
  const trusted = SHOW_TRUSTED
    ? `
    <section class="trusted">
      <p class="trusted-label">${esc(TRUSTED_LABEL)}</p>
      <div class="trusted-marquee">
        <div class="trusted-track">
          ${[...TRUSTED_BY, ...TRUSTED_BY]
            .map(
              (t) =>
                `<span class="trusted-item mark-${t.mark}">${esc(t.name)}</span>`
            )
            .join("")}
        </div>
      </div>
    </section>`
    : "";

  // "X and LinkedIn" rather than "X, LinkedIn": two items take a conjunction.
  // Built from the list so adding a third does not produce a dangling "and".
  const followLinks = ROADMAP_FOLLOW.links
    .map(
      (l) =>
        `<a href="${l.url}" target="_blank" rel="noopener noreferrer">${esc(l.label)}</a>`
    )
    .reduce((acc, link, i, all) =>
      i === 0 ? link : i === all.length - 1 ? `${acc} and ${link}` : `${acc}, ${link}`
    );

  host.innerHTML = `
    <section class="roadmap">
      <p class="roadmap-title">${esc(ROADMAP_TITLE)}</p>
      <ol class="roadmap-list">
        ${ROADMAP_TRACKS.map(
          (t) => `
          <li>
            <span class="roadmap-name">${esc(t.name)}</span>
            <span class="roadmap-body">${esc(t.body)}</span>
          </li>`
        ).join("")}
      </ol>
      <p class="roadmap-follow">
        ${esc(ROADMAP_FOLLOW.before)} ${followLinks} ${esc(ROADMAP_FOLLOW.after)}
      </p>
    </section>

    <section class="about">
      <a class="about-portrait" href="${ABOUT.homepage}"
         target="_blank" rel="noopener noreferrer"
         title="${esc(ABOUT.homepageLabel)}">
        <img src="${assetUrl(ABOUT.photo)}" width="320" height="320"
             loading="lazy" decoding="async"
             alt="${esc(ABOUT.photoAlt)}">
        <span>${esc(ABOUT.homepageLabel)} &#8599;</span>
      </a>
      <div class="about-body">
        <h2>${esc(ABOUT.title)}</h2>
        ${ABOUT.body.map((p) => `<p>${esc(p)}</p>`).join("")}
        <p class="about-quote">
          &ldquo;${esc(ABOUT.quote)}&rdquo;
          <cite>${esc(ABOUT.attribution)}</cite>
        </p>
      </div>
    </section>
    ${trusted}
    <footer class="landing-footer">
      <p>
        &copy; ${SITE.year}
        <a href="${SITE.authorUrl}" target="_blank" rel="noopener noreferrer">${esc(
          SITE.author
        )}</a>.
        ${esc(SITE.brand)} is free and open; your code and progress never leave
        this browser.
      </p>
    </footer>`;
}
