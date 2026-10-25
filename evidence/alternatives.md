# Existing alternatives: what they actually offer (problem 5)

**How this was checked.** 2026-10-25, 02:21–02:26 UTC. There was one researcher agent per product and a separate checker that re-opened every source and kept, relabeled or rejected each claim. Only public pages were used: no login, no forms, no API, no bulk crawling. events.yale.edu disallows crawling in robots.txt, so it was read with only 3 page views, like a person would. Statuses:
- **observed**: seen on a public page at the check time.
- **documented**: stated in the vendor's or provider's official docs.
- **not_tested**: needs a login or an actual product run.
- **not_found**: looked for where it should be and not seen.

Claims the checker rejected as overclaims are left out (see the end). Counts such as "62 events" are snapshots taken at the check time.

**Fairness rules.**
- Each product is described by what it actually does in its own setting.
- ChatGPT was **not run**, so its answers to our cases are **not tested**.
- Our internal keyword-vs-purpose comparison (evidence/q05_cases.md) compares two ways of treating the same candidates *inside this app*. It is not evidence that this app beats any of these products, and it says nothing about benefits to users.

## Yale-Localist (events.yale.edu)

| Dimension | Status | What was found | Source |
|---|---|---|---|
| Search/filters | observed | Keyword search, date picker, Experience filter (In-Person / Virtual), Event Types, Topics and Audience facets with counts; sort by Date/Name/Popularity; "Hide recurring events" | https://events.yale.edu/ |
| Audience | observed | Audience facet includes "Graduate & Professional (62)" and "Ages 21 Up (8)" (counts at check time) | https://events.yale.edu/ |
| Department/location filter | not_found | No department/group or location filter in the main filter panel; places and groups are separate browse pages | https://events.yale.edu/ |
| Topics | observed | Topic list includes "AI (Artificial Intelligence)", showing 0 events at check time | https://events.yale.edu/ |
| Registration | observed | Event cards have "Register" buttons, some to external pages and some to built-in ticketing. Whether open/closed status, deadlines or capacity are shown on detail pages was **not checked** (no detail page opened, because of the robots limit) | https://events.yale.edu/ |
| Registration (platform) | documented | Localist supports "paid, free and donation-based tickets" | https://www.localist.com/online-website-event-calendar |
| Personalization | observed | Opt-in "Digest" email ("Get a personalized list of events in your inbox"); "I'm Interested" buttons; Upcoming and Trending tabs. No "recommended for you" seen | https://events.yale.edu/ |
| Groups | observed | A groups directory (21 pages) of event-hosting units; page 1 showed no follow/join actions | https://events.yale.edu/browse/groups |
| Sources feeding it | not_found | The page does not say which systems feed the calendar; it accepts public event submissions | https://events.yale.edu/ |
| Aggregation (platform) | documented | "Localist aggregates your events into a single interactive calendar" | https://www.localist.com/online-website-event-calendar |
| Why an item is shown | not_found | No per-item explanation; ordering comes from filters and sorting | https://events.yale.edu/ |
| Login | observed | Listings are public; Yale NetID log-in exists. What requires sign-in was not tested | https://events.yale.edu/ |

## YaleConnect (yaleconnect.yale.edu, CampusGroups)

| Dimension | Status | What was found | Source |
|---|---|---|---|
| Coverage | observed | Public directory: "Load all 1376 groups". Group types include Yale College organizations and graduate/professional schools (e.g. Medicine, Law, GSAS) | https://yaleconnect.yale.edu/home/groups/ |
| SOM | not_found | No SOM group-type filter among about 54 types. This does **not** show that SOM groups are absent; a full search was not done | https://yaleconnect.yale.edu/home/groups/ |
| Groups as communities | observed | Persistent group pages, e.g. the Yale Photography Society page: "Join this vibrant community of Yale photographers…", 179 members, "There are no upcoming events" | https://yaleconnect.yale.edu/ycyalephotographysociety/home/ |
| Directory filters | observed | Category filter (e.g. "Arts: Visual Arts", "Sports/Outdoors"), school/type filter, Active/Archived, sort options | https://yaleconnect.yale.edu/home/groups/ |
| Event filters | observed | Date range, upcoming/past, location type (Online Only, Hybrid), event type, host group, tags | https://yaleconnect.yale.edu/events |
| Event keyword search (platform) | documented | "You can search the list for keywords, or use the filters to narrow the list." | https://helpcenter.readyeducation.com/exploring-and-attending-events |
| Event records without login | not_tested | Event lists rendered only as template placeholders in a logged-out fetch | https://yaleconnect.yale.edu/events |
| Registration/eligibility | not_tested | The UI has "Registered" / "Waiting List" labels and a Register flow; no real event's status, deadline or eligibility could be seen logged out | https://yaleconnect.yale.edu/events |
| Personalization (platform) | documented | A "Discover" feature: "Easily see events, groups and users that align with your interests." Whether Yale has it enabled was **not verified** | https://readyedu.atlassian.net/wiki/spaces/CGSD/pages/310837249/Getting+Started |
| Personalization (logged out) | not_found | No "recommended for you" on the logged-out pages viewed | https://yaleconnect.yale.edu/ |
| Why an item is shown | not_found | No explanation of why an event or group is shown, beyond "align with your interests" | vendor help pages above |
| Outside sources | not_tested | Whether it imports events from outside its own groups was not tested | https://yaleconnect.yale.edu/home/groups/ |
| Login | observed | Landing page, directory and group pages load logged out; some groups are "restricted to Yale University users" | https://yaleconnect.yale.edu/home/groups/ |

## Ordinary ChatGPT (chatgpt.com)

ChatGPT was **not run**. OpenAI's help pages returned HTTP 403 to direct fetches, so the "documented" rows rest on help.openai.com search excerpts and should be re-read in a browser before the report cites them.

| Dimension | Status | What was found | Source |
|---|---|---|---|
| Web search | documented | Search sends a rewritten query to third-party search providers (without the user's IP or account information) | https://help.openai.com/en/articles/9237897-searching-the-web-with-chatgpt |
| Availability | documented | Web search on the Free, Go, Plus, Pro, Business, Enterprise and Edu plans, and also logged out | https://help.openai.com/en/articles/9125172-the-chatgpt-home-page |
| Citations | documented | Answers may include inline citations and a "Sources" list; nothing about explaining fit | https://help.openai.com/en/articles/9237897-searching-the-web-with-chatgpt |
| Accuracy caveat | documented | Results and citations can be incomplete, outdated or incorrect; users are advised to open and check the source | https://help.openai.com/en/articles/8313428-does-chatgpt-tell-the-truth |
| Workspace freshness | documented | An "offline web search" mode for workspaces uses indexed and cached content that may be older | https://help.openai.com/en/articles/20001203-offline-web-search-for-chatgpt-workspaces |
| Structured filters | not_tested | Only natural-language refinement seen in the excerpts; the full article could not be read | (as above) |
| Finds CAW darkroom or YCGS events for our cases | not_tested | Needs an actual run | https://chatgpt.com/ |
| Shows prerequisites, audience, closed registration | not_tested | Needs an actual run | https://chatgpt.com/ |
| Returns ongoing communities, not just events | not_tested | Needs an actual run | https://chatgpt.com/ |
| Invents or misdates events | not_tested | Needs an actual run; only the general caveat above is documented | https://help.openai.com/en/articles/8313428-does-chatgpt-tell-the-truth |

## What this means for "What's new" (honest positioning)

- **Not new:** a campus event calendar with keyword, date, format, topic and audience filters (Localist has these). A group directory with communities and interest-based discovery (YaleConnect has groups; its platform documents a Discover feature). Web search with cited sources (ChatGPT, documented).
- **Differences this app can show and check:**
  1. Listings from organizers outside both platforms (a New Haven nonprofit and an official Yale center's own site), stored with the page wording behind each field.
  2. The user's **purpose** and conditions in plain words, turned into explicit checks against each listing's stated conditions: prerequisite, audience, age, membership, closed registration, play vs. watch, format and time. The result is "excluded", "check first" or "match", with reasons.
  3. A **per-item explanation** whose quotes are checked word for word by code, with unsupported details removed.
  4. Honest unknowns ("not stated on the page") instead of silent omissions.
- **Not shown, and must not be claimed:** that Localist or YaleConnect cannot show eligibility (their detail pages and logged-in views were not tested); that ChatGPT would answer our cases worse (not run); that students find more or better activities with this app (no user test yet).

## Claims rejected by the checker (left out above)

- YaleConnect: the claim that eligibility appears only in free text overclaimed one directory listing.
- ChatGPT: the claims about how search is triggered and about memory/location influence; the help page text was not readable (HTTP 403), so these could not be confirmed as stated.
