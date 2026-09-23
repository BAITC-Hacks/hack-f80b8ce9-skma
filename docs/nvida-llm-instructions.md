Which NVIDIA model fits
Our assistant needs three things from a model:

Tool calling. Without it, search, analogs and the cart don't work.
Good Russian. Kazakh is a bonus.
Speed. One chat reply takes 2–4 model calls.
These catalog models support tool calling (source):

Model	Why
meta/llama-3.3-70b-instruct	Safe first choice: stable tool calling, decent Russian
Nemotron-3-Super, Qwen 2.5 72B, Kimi K2, GLM 4.7	Alternatives. Qwen and Kimi are usually stronger in Russian
I only checked the model names in public sources, not with a key. Before using one, confirm on its card at build.nvidia.com that it supports Tool calling and copy the exact ID.

How to get the key
Go to build.nvidia.com and sign in with an NVIDIA account (free to create).
Open a model card, for example Llama 3.3 70B, and click "Get API Key" (or use the API Keys section in your profile).
Click Generate Key and copy the key. It starts with nvapi-.
On sign-up you get about 1,000 free credits, and you can request up to 5,000. The rate limit is about 40 requests per minute (source). Since one chat reply uses 2–4 model calls, that's enough for about 10–20 chat messages per minute: fine for a demo, tight for a busy one.

How to connect it
The app reads only the OPENAI_* variables. The NVIDIA_API_KEY line in creds.md isn't used. In backend/.env, comment out the OpenAI lines and add:


# OpenAI (current):
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.4-mini

OPENAI_BASE_URL=https://integrate.api.nvidia.com/v1
OPENAI_API_KEY=nvapi-...
OPENAI_MODEL=meta/llama-3.3-70b-instruct
OPENAI_REASONING_EFFORT=
Leave OPENAI_REASONING_EFFORT empty: it's only for OpenAI reasoning models.

Then compare the models on our demo questions and restart:


make llm-smoke MODELS="meta/llama-3.3-70b-instruct qwen/qwen2.5-72b-instruct"
make up
llm-smoke shows each model's answers, which tools it called and the time. Earlier, the same check showed that gpt-4.1-mini got one of the four questions wrong. If an NVIDIA model answers slower or worse than gpt-5.4-mini, keep OpenAI for the demo.

Once you have the nvapi- key, I can run the comparison and write up the results.