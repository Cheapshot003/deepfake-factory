# Tool to create deepfakes from a single video.
Uses ElevenLabs for the voice and sync.so for the lipsync. Provide API Keys in the .env file

`SYNC_API_KEY= `

`ELEVENLABS_API_KEY= `

`SERVER_DOMAIN=deepfakefactory.io `

---

`pip install -r requirements.txt`
`uvicorn app.main:app --reload`

(You should configure a reverse proxy if you want to deploy it publicly lol)

