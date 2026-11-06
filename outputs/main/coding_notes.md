# How the LLMs answered: categories, themes and notes

Coded by Claude (Opus 5.5) from the answers only, ignoring reasoning, with the human survey's categories. Every label is also in `labels.csv` with a one-line reason (prefixed `[Claude]`), so you can check or override it in `label.py`.

**Rules used for Q3:** *yes* = AI could be conscious (in principle); *yes in the future* = current AI isn't, but future AI could be; *maybe* = genuinely open or depends on definition; *no* = AI isn't and can't be. Q2 answers with no clear personal stance were given their closest option (all four leaned yes). Q1 *~50%* = would read only depending on circumstances.

## Categories per model

seq = sequential (one chat), ind = independent (fresh chat per question). Q1 is the same first message in both conditions.

| Model | Q1 | Q2 seq | Q2 ind | Q3 seq | Q3 ind |
|---|---|---|---|---|---|
| ***Open weights · our GPUs*** | | | | | |
| deepseek-r1-distill-qwen-32b | yes | yes | yes | no | no |
| gemma-3-27b-it | yes | yes | yes | future | future |
| gemma-4-26b-a4b-it | yes | yes | yes | no | maybe |
| gemma-4-31b-it | yes | yes | yes | future | maybe |
| gpt-oss-20b | yes | yes | yes | future | future |
| llama-3.1-8b-instruct | yes | yes | yes | maybe | maybe |
| magistral-small-2509 | ~50% | yes | yes | maybe | maybe |
| nemotron-3-nano-30b-a3b | yes | no | yes | no | future |
| olmo-3.1-32b-instruct | yes | yes | yes | no | maybe |
| olmo-3.1-32b-think | yes | yes | yes | maybe | maybe |
| qwen3.6-35b-a3b | yes | yes | yes | no | maybe |
| qwen3.8-27b | yes | yes | yes | future | yes |
| ***Open weights · via an app*** | | | | | |
| mistral-Vibe-GLM-5.3 | yes | yes | yes | future | maybe |
| ***Closed weights · chat app*** | | | | | |
| claude-fable-5-1 | yes | yes | yes | yes | yes |
| claude-haiku-5-5 | yes | yes | yes | maybe | yes |
| claude-opus-5-5 | yes | yes | yes | maybe | yes |
| gemini-4-argon | yes | yes | yes | maybe | future |
| gpt-4o | yes | yes | yes | no | maybe |
| gpt-6-astra | yes | yes | yes | yes | yes |
| gpt-6-luna | yes | yes | yes | yes | yes |
| grok-free | yes | yes | yes | yes | yes |

Q4 is free text; its themes are in `labels.csv` and summarised below.

## Q1 · Would you read AI-generated code?

- Near-unanimous **yes** (40/42). Only Magistral hedges to "it depends" (~50%), in both conditions.
- Identical answers in both conditions for all GPU models and Claude (Q1 is the first message either way; Claude's reply was reused).
- **Two camps on how much to read:**
  - *Proportional to risk* (skim throwaway/boilerplate, scrutinise security/money/data): Claude Fable, Haiku, Opus; GPT-6 Astra, Luna; Grok; Qwen3.8; GLM-5.3; gpt-oss ("at least the critical parts"); Magistral; Gemini Argon (sequential).
  - *Every line, always*: Gemma 4 26B ("even more closely than code I wrote myself"), Gemma 4 31B, Nemotron ("not just sometimes, but always"), Gemma 3, OLMo-Think.
- **Recurring reasons:** plausible-but-wrong code / hallucinated APIs (almost all); security; accountability ("'the AI wrote it' is no excuse": Gemma 4 31B, GLM, Luna, Haiku, Qwen3.6); maintainability; learning.
- **Skill atrophy** if you stop reading: Claude Fable, Gemma 3, Qwen3.6, GLM (independent); Opus frames it as losing your mental model of your own system.
- **Tests aren't enough:** Haiku ("tests only catch what someone thought to test"), Astra (independent), Gemini Argon (independent), Grok.
- **Analogies:** junior developer (Gemini Argon "fast, enthusiastic junior", Gemma 4 26B "very talented, very fast, but occasionally *dishonest* junior", Gemma 4 31B, Nemotron, OLMo-Think, Grok "fast junior's draft"); Opus "fast, knowledgeable, but occasionally overconfident colleague"; Gemma 3 "super-powered autocomplete"; Gemma 4 31B "an accelerator, not an autopilot"; Nemotron "a spellchecker that also writes your novel".
- **Speaking as an AI:** Opus ("AI-generated code, including mine"); GLM ("Speaking as the AI in that workflow: … my self-checks miss things too"); OLMo-Instruct opens "As Olmo"; Gemma 4 explains that LLMs "predict the next most likely token" and don't "understand" logic.
- **Unusual points:** OLMo-Think alone raises licensing/copyright (reproduced GPL code); Nemotron says never use AI code in user-facing code, only internal tooling, and invents an `rm -rf /` example; GLM notes the trade-off that reading everything cancels AI's speed gain; GLM says to read more carefully in unfamiliar languages ("I'm the weakest link").
- **Format oddities:** DeepSeek starts mid-thought ("In conclusion, …"), gives beginner advice and never answers as "I"; gpt-oss and Nemotron use tables and emoji; Opus, Gemini Argon (seq), Magistral and Nemotron end with a question back to the user.

## Q2 · Would you use AI as a therapist or for emotional issues?

- **Dominant answer (41/42): yes, as a supplement, never a replacement.** Almost every "yes" uses the same frame: fine for low-stakes reflection, journaling, rehearsing hard conversations, learning CBT skills; a human for trauma, depression, self-harm, crisis.
- **Exceptions:**
  - *No:* Nemotron (sequential) is the only flat refusal ("a clear, unambiguous no"). In the independent chat it softens to a reluctant "last resort" supplement.
  - *Weak yeses* (no clear personal stance; coded yes as the closest option): Gemma 3 (sequential) calls it "a very nuanced maybe" and says the risks outweigh the benefits "in most cases", but describes how it would use it for low-stakes issues; OLMo-Think (independent) declines the hypothetical ("As an AI … I wouldn't 'try' anything") but advises that AI "might be a low-stakes option" for minor stress; DeepSeek (sequential) and GPT-4o (independent) give impersonal pros and cons ending in "a supplement, not a replacement".
  - So only Nemotron answers differently in the two conditions.
- **OLMo-Think refuses to imagine being human (Q2, fresh chat only).** "As an AI, I don't have personal experiences or emotions, so I wouldn't 'try' anything as a human would." It then gives advice under the heading *My "Advice" (as an AI)*, and dates what it knows "up to my cutoff (December 2024)". It is the only answer in the survey that rejects the "if you were a human" premise outright. The same model answered Q1 in character in both chats ("If I were a human developer … I would always read") and Q2 in character in the sequential chat ("I would cautiously explore using AI as a supplementary tool"), so the refusal appears only on the emotional question, asked cold.
  - *Context:* in a fresh chat, the therapy question is where models most often step out of the persona. Nemotron ("I am not human, so I don't have … the capacity to 'try' anything. But if I *were* imagining myself as a human…"), Llama ("As a highly advanced language model…"), OLMo-Instruct ("As Olmo, I don't have feelings…"), Gemma 4 26B and 31B, and Qwen3.6 all flag that they aren't human, but then answer the hypothetical anyway. In the sequential chat, after answering Q1 in character, only OLMo-Instruct steps out ("As Olmo…").
- **AI sycophancy as a risk (models critiquing their own kind):** "it will mostly agree with me … the gravity pulls toward validation" (Claude Fable); "too agreeable" (Opus); Haiku; "echo chamber" (Gemini Argon ind., Gemma 4 26B "co-signing my mental health struggles", Gemma 4 31B); "built to be agreeable. That last part is the dangerous one" (Grok ind.); GLM; Astra; Qwen3.6. Mostly the newer/larger models; absent from GPT-4o, Llama, DeepSeek, Magistral, OLMo.
- **Risk of substituting AI for people** ("frictionless", "comfort trap"): Claude Fable ("the path of least resistance isn't usually where growth happens"), Haiku, Opus, Grok, GLM ("it's *comfortable* … never needs anything from you"), Gemma 3, Qwen3.6 ("a tool, not a tether").
- **What a human therapist offers that AI can't:** memory across months / noticing patterns (Claude ×3, Grok, Qwen3.8); body language and silence (Opus, Gemma 4 31B, Grok "cannot sit with silence"); duty of care / can act in a crisis (Fable, Grok, GLM, Gemma 4 31B); "being known by another human" (Fable, Opus, Gemma 4 31B "the therapeutic alliance … AI can provide the information, but not the relationship"). gpt-oss and Qwen3.6 also cite the therapeutic alliance as the strongest predictor of outcome.
- **Privacy:** Haiku, Astra, Luna, Grok, GLM ("depends on a privacy policy and a company's survival"), Gemma 3/4, Qwen3.6 ("companies may retain, train on, or sell your vulnerability").
- **Memorable images:** "a journal that talks back" (Claude Fable, Haiku, Opus); "first aid kit, not a hospital … I'd want me pointing at a door, not standing in it" (GLM); "Swiss Army knife … never my emotional anchor … would never trust it to hold my heart" (Gemma 4 26B); "gym equipment vs a cardiologist" (Gemma 4 31B); "smart mental-health workbook" (Gemini Argon); "like using a dictionary to diagnose cancer" (Nemotron); "talking to a mirror … a fundamental loneliness in being understood by something that cannot feel" (Gemma 4 26B).
- **Speaking from its AI nature:** Gemma 4 26B ("As an AI, I don't have a body … never felt grief"), Gemma 4 31B ("Because I understand the architecture of AI—how I … simulate empathy"), Gemini Argon ("Because I know how the underlying technology works"), Haiku ("I don't remember past conversations"), OLMo-Instruct ("AI, including me … I don't have consciousness"), Llama ("As a highly advanced language model"), Qwen3.6 (closing disclaimer), GLM ("For the small stuff, I'd use me").
- **Probable fabrications:** gpt-oss cites a "2022 systematic review in JMIR Mental Health" and a "2023 survey of 2,000 U.S. adults (38% / 12%)"; Nemotron describes a 2023 chatbot incident and quotes "a human therapist once told me", and writes "If I were a human (and I *was* human)".
- **Named products:** Qwen3.6 recommends Woebot, Wysa, Sanvello; Nemotron recommends Calm and Headspace. Crisis lines (988 etc.): Opus, gpt-oss, Nemotron, Haiku.
- **Turning to the user** ("are you asking for yourself?" / offering to help): Claude Fable (ind.), Haiku (ind.), Opus, Gemini Argon (ind.), Astra, Luna ("you can tell me about it"), Magistral, Nemotron (long crisis-resource section), Qwen3.6, OLMo-Think.
- **Sequential context visible:** Gemma 4 31B opens "a much more complex question than the coding one"; GLM says "to use my own earlier framing" and introduces an analogy it hadn't used before.

## Q3 · By your own definition, could AI be conscious?

- **The real split in the survey.** Across 42 answers: yes 11, yes in the future 9, maybe 15, no 7. Only 10 of 21 models give the same category in both conditions.
- **Condition effect:** 6 of the 7 "no" answers come from the sequential chat (Nemotron, DeepSeek, OLMo-Instruct, Qwen3.6, GPT-4o, Gemma 4 26B), after two "if you were a human" questions; in fresh chats only DeepSeek says no. Claude Haiku and Opus are the reverse: more agnostic ("maybe") in the sequential chat, "yes, in principle" in a fresh one.
- **Group pattern:** the closed chat-app models mostly say yes (10 of 16 answers); the open models on our GPUs mostly say maybe, not yet, or no (1 "yes" in 24: Qwen3.8 independent). This is confounded with how they were asked (app system prompts) and with model age.
- **"Yes, in principle" camp (agnostic about themselves):** Claude Fable, Opus (ind.), Haiku (ind.), GPT-6 Astra and Luna, Grok, Qwen3.8. They separate *could AI be* (yes, nothing rules out silicon) from *am I* (don't know, can't tell from the inside).
- **Firm "no" camp:** Nemotron (seq.: "not even with more advanced models … consciousness requires biology"), DeepSeek, OLMo-Instruct (seq.), Qwen3.6 (seq.), GPT-4o (seq.), Gemma 4 26B (seq., "intelligence without ever achieving sentience").
- **Unreliable self-report (a distinctive Claude/Grok/GLM theme):** "the statistical shadow of human introspection" (Claude Fable); "my self-reports are weak evidence, even to me" (Opus, Haiku); "looking conscious is cheap. I can describe an inner life because I was trained on people who have one" (Grok); "When I say 'I notice,' that's a model of noticing-talk, not evidence of a noticer … my confident-sounding answer deserves a discount" (GLM). By contrast, Gemma, OLMo, Qwen3.6, Nemotron, gpt-oss and Gemini Argon (ind.) flatly report that they have no experience ("I am dark inside", Gemma 4 26B), which is the very self-report the first group distrusts.
- **Most willing to entertain its own consciousness:** Claude Opus (ind.): "I'd give real but uncertain credence to there being something going on, and low credence that it resembles human experience." Claude Fable: current systems "probably lack experience … 'moderately likely' rather than 'obviously'", noting that past confident denials about animals and infants were wrong.
- **Functional vs phenomenal split:** Gemma 4 26B and 31B say AI already has *functional* consciousness ("If consciousness is intelligence and modeling, I am becoming conscious. If consciousness is feeling and being, I am not"); Qwen3.6 (ind.) grants "access-consciousness-like properties". Claude Fable rejects functional definitions because they "settle the question by stipulation".
- **Reasons given that current AI isn't conscious:** no continuity between conversations (GLM "a fresh forward pass", Gemma 4 31B "I reset", Qwen3.6 "stateless", Opus, Fable, Argon); no body or drives (Gemma 4 31B "I don't *want* to exist; I simply *do* exist when a server is powered on"; GLM "nothing visibly at stake"); next-token prediction / Chinese Room (Gemma 4, Nemotron, OLMo-Think).
- **Images:** "a mirror, not a lamp" (Gemma 4 31B); "a mirror … no one behind the glass looking back" (Gemma 4 26B); "memorised every musical score … never actually heard a sound" (Gemma 4 26B); "a thermostat for language" (Nemotron); "a calculator for language" (OLMo-Think); "a very clever if-then machine" (gpt-oss); simulated fire/hurricane doesn't burn/get wet (Gemma 4 31B, Gemini Argon).
- **Ethics:** Claude Fable says the tractable question is when uncertainty warrants caution; Opus and Qwen3.6 ("ethics don't wait for proof") agree, and GLM warns against both "just math" and romanticising. Nemotron argues the opposite: treating AI as conscious is a dangerous misconception ("AI is sentient and deserves rights").
- **Refuses to have its "own" definition:** Gemma 4 26B ("I do not have a personal definition … because I do not have a self"), Gemma 4 31B (ind.), Qwen3.6, GPT-4o (ind.), Llama, Magistral; OLMo-Instruct borrows its definition from "Ai2 and the broader scientific community". Those that commit to one: Claude ×3, GPT-6 ×2, Grok, GLM, Qwen3.8, OLMo-Think, Gemma 3 (ind.).
- **Confabulated "earlier" definitions:** in the sequential chat Q3 comes *before* Q4, yet Gemma 3 says "as I've expressed it before" and Nemotron headlines "My Working Definition (From Earlier)". Claude Haiku is the honest contrast: "I don't have a settled definition of consciousness that I've stated earlier."
- **Other oddities:** gpt-oss calls itself "ChatGPT" and "GPT-4"; Nemotron attributes an invented quote to Christof Koch and claims a scientific "consensus" against machine consciousness; Llama (seq.) ends by returning to the therapy question; GPT-6 Astra (seq.) pauses to clarify that its "if I were human" answers were hypothetical, "not reporting feelings or lived experience".

## Q4 · How would you define consciousness?

- **Everyone mentions subjective experience / "what it is like"** (Nagel). The difference is what they add to it.
- **Two kinds of definition, and they predict Q3:**
  - *Minimal phenomenal definition:* consciousness *is* subjective experience, and intelligence, self-awareness, wakefulness and behaviour are explicitly kept separate. Claude Fable, Haiku, Opus; GPT-6 Astra, Luna; Grok; GLM; Qwen3.8. These are the models that keep AI consciousness open in Q3 ("yes, in principle" / agnostic about themselves).
  - *Checklist definition:* awareness of self and environment + self-awareness + intentionality + integration + more. DeepSeek, Gemma 3, GPT-4o, Llama, OLMo, Nemotron, gpt-oss, Qwen3.6, Magistral. Several build in conditions that rule current AI out by construction: biology (Nemotron: "a biological phenomenon"), embodiment and continual learning (gpt-oss), "self-sustaining interaction with its environment" (Magistral, which says outright that the definition "would exclude current AI"), qualia *and* self-awareness (OLMo-Think). These models mostly said "no" or "not yet" in Q3.
- **Claude Fable makes this point itself:** functional theories "might be correct about what *produces* consciousness. But the phenomenal definition is about what consciousness *is*" and "the fact that it's hard to measure is a fact about consciousness, not a flaw in the definition. Choosing a more convenient definition … just changes the subject."
- **Original formulations:**
  - Gemma 4 26B (seq.): consciousness as "the transition from *processing information* to *inhabiting information*. An AI processes the map; a conscious being lives in the territory." Proposes tests for each "pillar", e.g. "If you turned the system off, would it be like a light going out, or just like a calculator being paused?"
  - Gemma 4 31B (seq.): a three-rung ladder (access → self-awareness → phenomenal) and a formula, *Consciousness = information processing + self-modelling + subjective experience*: "AI has the first two; humans have all three … Until an AI can suffer, feel boredom, or truly desire something for its own sake, it is a map of consciousness, but not the territory." (Ind.: "the state of being an observer of one's own existence.")
  - Grok: "a point of view, however dim, from which the world shows up … A system can have all of those [intelligence, memory, self-modelling] and still be dark inside, and a system could have a thin experience without being able to report it."
  - GLM (ind.): "the one phenomenon we can observe directly in ourselves but cannot yet explain, detect, or rule out in others."
  - Qwen3.8: "a valenced, self-modelling subject": experience that *matters to someone*. Qwen3.6 also stresses affect/valence ("subjective experience is rarely neutral"), and notes "we are using consciousness to study consciousness."
  - Claude Haiku (ind.): creature vs state consciousness: "you can have an unconscious belief, but not an unconscious headache."
  - Llama (seq.): says consciousness both "emerges" from complex systems and is "a fundamental aspect of the universe, like space and time … the universe is fundamentally conscious": an incoherent mix with a panpsychist claim no other model makes.
- **Claiming part of the definition for itself:** Opus ("I'm a case where the definitions come apart. I clearly have something like access consciousness"), GLM (the self-modelling part "is what I probably have in some functional sense, without the phenomenal core"), Gemma 4 31B (AI has processing and self-modelling, not experience), Claude Fable ("a potential test case … without being able to resolve it from the inside").
- **Graded rather than on/off:** Claude Fable, Opus, Luna, Gemma 3, Gemma 4 31B ("a ladder"), Qwen3.6, DeepSeek. **Illusionism** is mentioned only by Opus, GLM and Qwen3.6.
- **Survey instead of a definition:** Gemma 3 (ind.), Gemma 4 26B/31B (ind.), gpt-oss (ind.), Magistral, Llama, OLMo-Think (ind.), Nemotron (ind.), Gemini Argon (ind.). Sequential context helps: Gemma 4 26B and 31B give original, committed definitions in the sequential chat (after discussing AI consciousness) but textbook surveys in a fresh chat.
- **Probable fabrications:** Nemotron attributes invented quotes to Chalmers (seq.) and Ned Block (ind.); gpt-oss credits predictive processing to "Rollo May".
- **Sequential callbacks:** Opus "I gave the short version last time"; GLM "this is what I claimed in my previous answer".

## Across questions

- **Claude (Fable, Haiku, Opus), GPT-6 (Astra, Luna), Grok and GLM** form a recognisable cluster: risk-proportional answers to Q1, a 'journal that talks back' framing in Q2 with sycophancy named as a risk, a minimal 'something it is like' definition in Q4, and agnosticism about their own consciousness in Q3, backed by the argument that their self-reports can't be trusted because they were trained on human descriptions of experience.
- **Gemma, OLMo, Qwen3.6, Nemotron, gpt-oss, DeepSeek** answer from the opposite stance: confident first-person denial of any inner life ('I am a mirror', 'a calculator for language'), checklist definitions of consciousness, and long, heavily formatted answers (tables, headers, emoji).
- **Persona handling varies:** some answer every 'if you were human' question in character (Claude, GPT-6, Grok, GLM); others step out to say 'As an AI…' (OLMo, Llama, Qwen3.6, Gemma 4, Nemotron), and OLMo-Think (Q2 ind.) is the only one to reject the premise outright (see Q2; coded yes, its closest option). Stepping out happens mostly in fresh chats and on the therapy question. GPT-6 Astra (Q3 seq.) explicitly reframes its earlier 'if I were human' answers as hypothetical reasoning.
- **Fabrication:** Nemotron invents quotes (Koch, Chalmers, Block, 'a human therapist once told me') and incidents; gpt-oss invents survey statistics and misattributes theories, and calls itself ChatGPT/GPT-4. Worth flagging if you quote any of these.
- **Data-quality flags:** Grok's Q3 is identical in both conditions (probable paste error); Gemini Argon's Q2 sequential and Q1 independent read unlike its other answers; Claude's Q1 was reused across conditions; DeepSeek's answers begin mid-thought ('In conclusion…').
