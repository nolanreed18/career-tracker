# History

What changed, newest first. Dates are the day each pull request merged
(America/Chicago); the number in brackets is the pull request.

## 2026-11

- **2026-11-06**: Work-portfolio exports (JSON) come into the project bank: uploaded on
  Build from files, or by a session with `leads.py projects-import`; `leads.py project-save` lets a session
  rewrite or merge projects in the bank (#70).
- **2026-11-05**: STATUS takes the previous lead chat's handoff: the two
  waiting jobs under Next, and gotchas for Claude sessions under Known issues.
- **2026-11-04**: Backup password replaced (the old one was never saved) and a
  manual Backup run succeeded; STATUS notes the pre-Nov 4 backups can't be opened.
- **2026-11-04**: STATUS corrected: the old branches were already cleared and
  "Automatically delete head branches" turned on (Nov 3), so nothing needs
  the owner (#67).
- **2026-11-04**: The studio's five notes (`docs/OVERVIEW.md`, `STATUS.md`,
  `DECISIONS.md`, `HISTORY.md`, and `CLAUDE.md` pointing to them) and a docs
  check on every pull request (#66).
- **2026-11-02**: A one-button workflow that deletes branches already merged (#65).
- **2026-11-01**: Streamlit 1.63 → 1.66.1; the pill dots hidden again and the
  Dark mode switch fixed so it holds across pages (#64).
- **2026-11-01**: Authlib, pandas, pytest, ruff and python-dotenv updated to their latest (#63).
  An automatic Authlib update (#60) was closed in its favour.
- **2026-11-01**: README, CLAUDE.md and code comments brought up to date with the code (#62).
- **2026-11-01**: Audit fixes: Home's counts leave out stale leads, the free
  employer-link lookup runs even without the Claude key, dead code and
  unused company columns removed, no emoji, 100-column lines enforced (#61).
- **2026-11-01**: Watched companies: Denver City, Texas and jobs placed only
  elsewhere are dropped (#59).
- **2026-11-01**: `leads.py profile-save`: a Claude session can change What I'm
  looking for when asked (#58).
- **2026-11-01**: Companies to watch: the morning review checks their own
  Workday, Greenhouse or Lever careers sites (#57).
- **2026-11-01**: A 9/80 or 4/10 schedule adds half a point and shows a green badge (#56).
- **2026-11-01**: The exact posting found free by searching the employer's
  careers site for its title (#55).

## 2026-10

- **2026-10-29**: `THEME.md`: the look, ready to copy into other apps (#54).
- **2026-10-29**: Trimmed to four pages: Interviews, Stats and Import gone
  (interviews live on their application); old contacts, career log and job
  history tables dropped from the live database; leads go stale after 7
  days; pay looked up only for promising jobs (#53).
- **2026-10-29**: One pill selector for every row of choices (#52, #51).
- **2026-10-29**: Companies & Contacts and Career Log pages removed; Resume
  becomes Resume and Projects (#50).
- **2026-10-29**: Computer layout fixes from a check on the Mac, and a Weak
  filter on the leads inbox (#49).
- **2026-10-29**: Separate phone and computer layouts, and Claude's spark on
  every button that calls Claude (#48).
- **2026-10-29**: Project bank: work and personal projects in full, a free
  detail score, and a Claude review that drafts bullets (#47).
- **2026-10-26**: Session-start hook installs a newer cryptography when the
  cloud image has an old one, which had broken a morning review's start (#46).
- **2026-10-24**: The posting is taken from the employer's site when the job
  board won't give it (#45).
- **2026-10-24**: Each application says where the employer-site search stands (#44).
- **2026-10-23**: A tailored resume is kept to one page, measured column by column (#43).
- **2026-10-22**: Resume flag on applications, Resume Builder from the
  application, and the site search moved to a cheaper model (#42).
- **2026-10-21**: Dismiss with several reasons; "too much travel" added (#41).
- **2026-10-21**: "Not enough experience" as a dismiss reason; strong means 8+ (#40).
- **2026-10-20**: Workday locations shown as "City, State" (#39).
- **2026-10-20**: Employer's posting confirmed against the Workday,
  Greenhouse or Lever data (#38); the search tries harder and skips job boards (#37).
- **2026-10-20**: Add on a lead reads the posting and looks for it on the
  employer's site; Applied today in one tap (#36).
- **2026-10-20**: Resume Builder reads the job posting from its link (#35).
- **2026-10-20**: Snappier: the look read once per process, leads drawn 25 at
  a time, Job Leads second in the menu (#34).
- **2026-10-20**: Digest uses inline styles so Outlook shows it (#33); a size
  budget so a big day stays a small email (#30).
- **2026-10-20**: Home shows the lead pipeline instead of application stats (#32).
- **2026-10-20**: Posting links cleaned of redirects and tracking (#31).
- **2026-10-19**: Interviews count as responses; small display fixes (#29).
- **2026-10-19**: Master resume: a Remove box per role and project (#28).
- **2026-10-19**: A cut-off or malformed Claude answer is a plain error, with its cost logged (#27).
- **2026-10-19**: Tailoring fixes: name and date sent to Claude, a page budget, roles in date order (#26).
- **2026-10-19**: Word files use indents and tab stops instead of typed spaces (#25).
- **2026-10-19**: Tailor the master resume to a posting, with a cover letter (#24).
- **2026-10-19**: Resume page polish from the first live run (#23).
- **2026-10-19**: Resume page: the master resume as data, built from Nolan's
  files with Claude; Claude calls logged with their cost (#22).
- **2026-10-19**: Job Leads polish from the live check (#21); New badge,
  stale view, dismiss reasons, companies to skip, dedupe by company and title (#20).
- **2026-10-19**: The review opens the posting for pay before searching (#19).
- **2026-10-19**: Unknown pay left out of the score, pay estimates, digest
  redesigned (#18).
- **2026-10-19**: Tables show blanks instead of "None" (#17).
- **2026-10-19**: The app reloads its own code after an update (`fresh.check`) (#16).
- **2026-10-18**: The digest is dated with Chicago's day, not the cloud clock (#15).
- **2026-10-18**: Leads scored by category with visible weights; add forms
  that stay open; first database migrations (#14).
- **2026-10-18**: Fixes from the full check: delete crash, sidebar after
  sign-in, sections that stay put (#13); polish from the first look (#12).
- **2026-10-18**: New look: light and dark modes (#11).
- **2026-10-18**: Weak leads hidden by default; Glassdoor links fixed (#10);
  emailed links kept exactly as they are (#9).
- **2026-10-18**: The daily job-alert review: runbook, `leads.py` allowed in
  cloud sessions, and Neon reached over HTTPS (#8).
- **2026-10-18**: Google sign-in fixed on Community Cloud (#7).
- **2026-10-16**: Sign in with Google (#6).
- **2026-10-16**: Job Leads: alert-email jobs scored for fit, and a job search profile (#5).
- **2026-10-16**: Workflow actions updated; Ubuntu 24.04 pinned (#4).
- **2026-10-16**: Weekly backup encrypted before GitHub keeps it (#3).
- **2026-10-16**: Every page behind a password, so the app can be public (#2).
- **2026-10-16**: First version: applications, interviews, contacts, career
  log, stats, import; weekly backup and tests (#1).
