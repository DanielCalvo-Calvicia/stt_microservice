# Q01 — Before the deployment tasks

> **Answered by the maintainer on 2026-11-06 and processed.** Question 1 is decision T-02.1 (option B; [ADR-009](../decisions/ADR-009-model-delivery-in-docker.md)); 2 to 4 accepted as recommended; 5, 8 to 13, 15 and 16 as recommended (the engine of the robot stays undecided); 6: English now, **Spanish in the future** (tests with a multilingual model, a Spanish measurement in T-03.6); 7: `UNKNOWN` (the tasks only report times); 14: Raspberry Pi 4B, 4 GB, 64-bit without desktop, Debian release unknown. Written into the tasks (see the *Plan revision 3* note of [../tasks/README.md](../tasks/README.md)); new task T-01.6 (pin the dependencies).

Written on 2026-11-06, after the deployment task plan of [docs/tasks](../tasks/README.md) was generated from the audit ([deployment_audit/stt.md](../deployment_audit/stt.md)). Every question is about `stt_microservice`, about how Brain uses it, or about how it is deployed.

Write your answer after `A:` (English or Spanish); `[x]` marks a choice; `UNKNOWN`, `NOT APPLICABLE` and `LATER` are valid answers; **never write secrets** (write *where* they live, not their values). Each question says why it matters and gives my **recommended** answer, so "Recommended" is a valid answer.

What this questionnaire collects: the plan has one decision that only you can take (question 1, it blocks the whole of T-02 and the Docker part of T-03), and a handful of facts about stt, your key and your machines that the tasks need before they can run. Everything else in the plan I could settle from the code.

**Most urgent (they block or change tasks):** 1, 5, 8, 11.

**Already decided and not asked again:** T-01.2.1, the shape of the local-model settings (option A, 2026-11-06). Question 13 only asks you to confirm how I wrote it down.

---

## A. How the local models reach the stt container (decision T-02.1; blocks T-02.2 to T-02.5 and the Docker tasks of T-03)

**Why it is asked.** A Docker container of stt loses its model cache every time it is recreated (the deploy tool does `docker rm -f` and then `docker run`, and has no volume support), and stt's `prepare` step runs when the image is *built*, with no `.env`, so it sees the defaults (OpenAI engine, gate off) and downloads nothing. Only the local engine and the wake-phrase gate need a model; the default engine, OpenAI, needs none. The full options and facts are in [T-02.1](../tasks/T-02_deployment-tool-changes/T-02.1_model-delivery-decision.md).

1. **Which option?**
   - (A) A named volume holds stt's model cache (`HF_HOME` inside it); the models download at the service's first start. Smallest change; the first start is slow, so `--health-timeout` and Brain's 60 s preflight must wait for it.
   - (B) A, plus the tool runs stt's `prepare` script once, in a throw-away container with the volume and the real `.env`, after the build and before the service starts (deploy, update, rollback). It is the Docker twin of the native `prepare` step.
   - (C) Bake the models into the image at build time (the model names travel as build arguments). No volume, but a bigger image and a rebuild to change a model.
   - (D) Change nothing: Docker supports `STT_ENGINE=openai`; a local engine runs natively, or re-downloads in every new container.

   *Recommended: (B).* A normal deploy never starts the service with an empty cache while the network is up, so the 60 s waits are safe, and the image stays free of models and secrets. Choose (A) if you accept a slow first start and want the smaller change, or (D) if Docker with a local engine is not something you want.
   A:B

2. **The volume.** If A or B: a volume named `oblivion-stt-models`, mounted at `/models`, with `HF_HOME=/models/huggingface` set by the tool **only for Docker**. A native install keeps the default cache. Acceptable?
   *Recommended: yes.*
   A:Yes

3. **A download that fails during `deploy`.** A warning and the deploy continues (as it does natively), or the deploy fails because stt needs the model?
   *Recommended: a warning and continue; the service then fails its own start with a clear error, and `deploy` reports it.*
   A:Recommended

4. **Deleting the volume.** Should `stop` or `rm` of stt ever delete it?
   *Recommended: never automatically. The manual names `docker volume rm oblivion-stt-models` for the operator.*
   A:Recommended

---

## B. The engine and the model (change what T-01 builds and what T-03 measures)

5. **What is the engine of the real robot?** Today `STT_ENGINE=openai` is the default: the audio of every utterance goes to OpenAI and every call is billed. The local engine keeps the audio on the machine but runs on the robot's CPU. This decides which engine the acceptance runs treat as the main one (T-01.1.3 is local, T-01.1.4 is OpenAI, T-03.2 and T-03.3 need a local one to prove the volume) and how much effort goes into the Raspberry Pi speed (T-03.6).
   - [ ] OpenAI in the real robot; local only for the wake-phrase gate and experiments
   - [ ] local in the real robot; OpenAI only as a fallback or for development
   - [ ] not decided; measure first
   *Recommended: not decided; keep OpenAI as the default and let T-01.1.3 and T-03.6 give the speed numbers, then decide.*
   A:Recommended

6. **Which languages must stt understand?** The default `STT_LANGUAGE` is `en` and the local model is `small.en` (English only) until the settings of T-01.2 exist. With the settings you could use a multilingual model (for example `small`), at a cost in speed on a Pi. If Spanish or another language matters, T-01.2.2 and T-01.2.3 get a test with a multilingual model name, and T-03.6 measures it.
   *Recommended: English only for now; the settings leave the door open.*
   A:Recommended, but on the future will be spanish

7. **How long may the text take?** After an utterance ends, how many seconds are acceptable before Brain has the text, on the PC and on the Pi? (For example 1.5 s and 4 s.) Without a number, T-01.1.3 and T-03.6 report the measured times and cannot say pass or fail.
   *Recommended: you give a number; if you do not know, say `UNKNOWN` and the tasks only report the times.*
   A:UNKOWN

---

## C. Scope of the plan

8. **What about `contracts` 0.16.0 in stt?** The working tree has stt's requirement files pointing at the 0.16.0 wheel, the 0.15.0 wheel deleted from `vendor/` and the 0.16.0 wheel untracked, while every stt document and the last commit say 0.15.0. I did not make that change. T-01.4 (the requirements split) edits the same two requirement files, so it must not undo or commit your edit by mistake. Options: (a) it is your work in progress, T-01.4 keeps the 0.16.0 lines as they are, and the stt documents move to 0.16.0 when you commit it; (b) it should not be there, and you will revert it yourself before T-01.4 runs.
   *Recommended: (a).*
   A:Recommended

9. **Limits and timeouts (NFR-8).** stt has no limit on a request body or an utterance, and no timeout or retry for the OpenAI call. The plan does not include them (the audit did not ask). Add an epic for them after T-01, or leave it as documented debt?
   *Recommended: leave it as documented debt for now; it is a code change with its own decisions (what size, what timeout), and it deserves its own questionnaire.*
   A:Recommended

10. **Pinned dependencies.** stt's runtime requirements are `>=` only. T-01.4 only splits the dev tools out; it does not pin. Pin after the real engines have run once (so the pins are versions that were proven), as a separate task?
    *Recommended: yes, separate and after T-01.1.3 and T-01.1.4.*
    A:Recommended

11. **Brain's 60 s wait for stt at start-up.** If a first start of stt with a local model takes longer than Brain's preflight wait (`STARTUP_PREFLIGHT_*`, 60 s by default; T-01.1.2 measures the real time), Brain can give up on stt even when the deploy tool waited longer. Should the plan stay inside stt and rely on `prepare` downloading the model first, or may a task also raise that wait in Brain's own settings, just for stt?
    *Recommended: stay inside stt and rely on `prepare`; raise Brain's wait only if the measured time proves `prepare` is not enough.*
    A:Recommended

---

## D. Your machines and permissions (the manual tasks T-01.1.2 to T-01.1.7 and T-03)

12. **Permission to run the real checks when you say "go".** T-01.1.2 deploys stt with the deploy tool, which writes under `deployment/` and downloads models (hundreds of MB). T-01.1.4 calls OpenAI with your key and spends a few cents. T-01.1.7 does the wake-phrase round trip through Brain with real audio. May I run each one as soon as you tell me "go" for that task, using the `config/local/` files you already keep, or do you want to run the commands yourself and paste the result?
    *Recommended: I run them, one task at a time, after your "go"; I never print or copy the key.*
    A:Recommended

13. **Confirm how the decision T-01.2.1 is written.** `STT_MODEL`, `STT_THREADS` and `STT_COMPUTE_TYPE`; threads and compute type shared by the main model and the gate; defaults `small.en` / `2` / `int8`; a blank value means the default; `0` threads is valid; a bad `STT_THREADS` stops the start with an error that names it; the compute type is passed through as written; the OpenAI model stays the constant `whisper-1`. It becomes ADR-008 when T-01.2.2 runs. Anything to change before it is written?
    *Recommended: no change.*
    A:Recommended

14. **stt on the Raspberry Pi.** T-03.6 (native install and speed) and T-03.7 (Docker on arm64) need a Pi. Which model and how much RAM, is the OS 64-bit (the portability check only resolved stt's wheels for 64-bit aarch64), is Docker installed on it, and is it reachable now through the Docker context `raspberry`? If it is not available yet, those two tasks wait and the rest of the plan does not.
    A:It is Raspberry 4b with 4GB. Raspberry pi 64bit no desktop (i dont remember if its bookworm or the other).

15. **Docker on this PC for the stt image.** Docker Desktop answered on 2026-11-06 (`desktop-linux`). The Docker tasks build stt's image (about a gigabyte) and download models. May I use it for T-03 once T-02 is done, with throw-away containers and volumes that I remove afterwards (only the ones I created)?
    *Recommended: yes.*
    A:Recommended

16. **The order you prefer.** The plan starts with T-01.1.1 (clean clone, install and the 90 tests, no download). After it, T-01.1.2 (deploy with the tool), T-01.1.6 (pipeline with fake hardware) and the code chain T-01.2.2 to T-01.2.3 can run in any order. Which matters most to you first: measuring what a fresh deploy really does (T-01.1), making the model a setting (T-01.2), or the Docker answer (T-02)?
    *Recommended: T-01.1 first, because its first-start timing feeds question 1.*
    A:Recommended
