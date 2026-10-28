# **PRD: Earner Onboarding Assistant**

[Ayush Shrote](mailto:ayush.shrote95@gmail.com) \| Drafted with Claude Code  
Oct 28, 2026

**About this document:**   
This PRD is a portfolio project inspired by my experience building LLM-based assistants in a risk and compliance setting at Uber. It is an independent exercise, not a description of any internal system. It covers the first phase of a larger initiative: building the assistant. A separate evals system and feedback loop will then drive its accuracy toward \~99%. All details and numbers are illustrative or invented, so please read them directionally.  
---

## **Context**

Earners (restaurants, fleets and drivers) must pass a series of onboarding checks before they can go online and earn on the marketplace. These checks verify that the earner is who they claim to be and is not involved in money laundering.

Each check requires the earner to upload proof of a different aspect of their identity, such as legal entity, business shareholders, and payment profile details. An onboarding agent (a human expert) then reviews the submission. If the information matches official sources, such as government or bank portals, the check passes. Once all checks pass, the earner can operate on the platform.

When an earner gets stuck at any check, i.e. the check has been pending or rejected beyond the expected review time, the delay is costly on both sides. The earner loses income, and the platform loses supply hours it could have used to serve demand. 

Earners get stuck for two broad reasons- 

1) **Earner-side**: they do not submit required documents for the check or submit incomplete, incorrect or unclear documents.  
2) **Platform-side**: the onboarding agents take too long to investigate why the earner is stuck and resolve it. 

This PRD addresses the platform-side causes by building the Earner Onboarding Assistant, a chatbot that helps onboarding agents investigate and resolve issues faster when an earner is stuck. The goal is faster agent handling time, which should translate to faster earner onboarding time which means more earners go online sooner \+ better platform metrics such as supply hours.

This PRD covers the first phase: building the assistant. A subsequent evals system and feedback loop, out of scope here, will measure and improve its answer accuracy over time.

## **Problem Statement**

Onboarding agents lack a fast, reliable way to see where earners are stuck and why. As a result, stuck earners wait longer, and many never go online.

**Earner: "I can't work until I have passed all the onboarding checks."**

- Cannot go online until every onboarding check is passed, so each hour of delay is an hour of lost earnings. Median onboarding takes 60 hours (p90: 450 hours).  
- For earners with longer onboarding time (\>p90), 40% of the total time is due to agent handling and queue time.   
- Longer onboarding time is associated to higher churn \- Entities for which onboarding time exceeds p90 are 10x more likely to churn and never operate on the platform as compared to entities where onboarding time \< p90

**Onboarding agent: "Every stuck earner is a manual investigation."**

- Each ticket from customer support requires manual investigation  
  - opening the portal  
  - searching for the earner  
  - reading check-level details  
  - working out the likely cause (for example, a document not uploaded)  
- Average handling time is 45 mins per earner  
- Agents review 7 earners per day, so handling time directly caps how many stuck earners are cleared daily  
- Faster handling frees capacity, which shortens the queue  
- The answer then travels back through customer support: platform-side blocks are actioned by the agent, and earner-side blocks are relayed to the earner

## **Users**

| User | Job to be done | Pain point | Typical question | Frequency |
| :---- | :---- | :---- | :---- | :---- |
| **Onboarding agents** | Unblock earners quickly and give a clear reason | Manual, multi-step investigation per ticket; limited earner reviews per day | "Where is earner P-10482 stuck, and why?" | \~5x avg. throughout the day per agent; 20 agents |
|  | Identify bottlenecks in onboarding  | Similar issues across many earners are resolved one by one, manually | “In Spain, which check do most restaurants get stuck on, and why?”  | Ad-hoc/ once a week; 3-4 senior agents |

## **Proposed Solution**

### Need

These problems share one root cause: the answers already exist in the onboarding data, but getting them requires manual investigation or an analyst’s bandwidth. 

Onboarding agents need to get accurate, verifiable answers about individual earners and about patterns across earners immediately, without manual effort or waiting on someone else. This would shorten investigations, make systemic problems easier to spot, and reduce agent handling time. Lower handling time frees agent capacity and shortens the queue, which should translate to faster earner onboarding.

### Goals

1. Answer entity lookups correctly with latest information  
   -  If failed then check and the reason  
2. Answer aggregate questions correctly   
   - By counts and percentages  
   - Support slicing by check and attributes for faster problem identification.  
3. Say "no data" where not available or ask a clarifying question instead of guessing.  
4. Refuse requests that expose earner identities for more than one earner.  
5. Refuse information that falls outside the above scope.

### Non-goals

- No write actions. The assistant never changes an earner's status.  
- No predictions or recommendations on what to do with an earner.  
- No access to free-text agent notes.  
- No non-English queries.  
- No automated alerting.

### MVP

The MVP is a natural-language chat assistant built on a pre-transformed data source. Every answer is grounded in that source and shows when the data was last updated. The assistant cannot answer from outside it. Each query, answer and agent feedback is logged, so the evals phase can be set-up later.

**Core Loop 1**   
An onboarding agent types in an earner ID and gets  
	\-\> **Passed** if all checks have passed  
\-\> **Failed**, with with each check that has not passed and its recorded failure reason, if any check has not passed  
\-\> **No Record Found**,  if the ID does not exist.

**Core Loop 2**  
An onboarding agent asks a cohort question, e.g. “What % of Region C earners who started in September are stuck on check 1 and why?" and gets  
\-\> The count, the percentage and a breakdown of top recorded failure reasons, which can be re-cut by other attributes  
\-\> A clarifying question when the request is ambiguous  
\-\> “No data” when the cohort is empty or the attribute is not in the source  
\-\> A decline for requests for bulk earner identities, cohorts below the minimum size, or anything out of scope

![][image1]  
(Chatbot mockup \- Core Loop 1 & 2\) 

## **Risks**

**Accuracy risks**

* Earner incorrectly marked as Passed/ Failed  
* Earner info provided where earner does not exist  
* Aggregate numbers are incorrectly reported  
* Failure reason not present in data is provided

**Security risks**

* Bulk earner identities exposed  
* Instruction hidden in a data field changes the assistant's behavior

**Operational risks**

* Unnecessary refusal of legitimate questions  
* Misreads typos, region aliases, or follow-up questions

## **Metrics**

**Primary Metric**

| Metric Name | Baseline | Target |
| :---- | :---: | :---: |
| **Average agent handling time per earner** Average time spent by an agent on taking action on an earner | 45 mins | 15 mins |

**Secondary Metrics**

| Metric Name | Baseline | Target |
| :---- | :---: | :---: |
| **Average queue time per earner** Average time an earner is blocked after they have provided the information till an agent starts investigation | 31 hours | Decrease |
| **Average earner onboarding time** Average time it takes for an earner to onboard on the platform and start earning  | 118 hours | Decrease |
| **Earners reviewed per agent/ day** Number of earners reviewed by an agent in a day | 7 earners/ day | Increase |
| **Queries/ day** Number of queries answered by the assistant in a day | \- | \~100 queries/ day |

**Guardrail Metrics**

| Metric Name | Baseline | Hypothesis |
| :---- | :---: | :---: |
| **Earner onboarding rate** Number of earners who passed onboarding/ Number of all incoming earners that onboard in a time period | 80% | Same |
| **Eval based metrics** (to be defined in evals and feedback stage of launch plan) |  |  |

## **Launch Plan**

The assistant launches only once it has proven its accuracy.

| Stage | What happens | Exit gate |
| ----- | ----- | ----- |
| 1\. Development | Build the assistant on the pre-transformed data source, with basic developer testing of both core loops. | Core loops work end to end |
| 2\. Evals and feedback | The evals system and feedback loop measure answers and drive accuracy up (out of scope for this PRD). | Accuracy reaches 99% |
| 3\. Dogfooding | Power users use the assistant on real work while accuracy is measured on their queries. | Accuracy stays above 99% for 2 consecutive weeks |

**Launch:** once the stage 3 gate is met, the assistant opens to all onboarding agents.

(Launch criteria will be based on metrics defined in evals and feedback stage.)