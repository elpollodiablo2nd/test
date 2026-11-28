# Thomas Baignères - Olvid - Concurrencer WhatsApp sans collecter une seule donnée — English Voxtral narration

- Episode page: https://podcast.ausha.co/in-security-we-trust/olvid-thomas-baigneres
- Original audio: https://audio.ausha.co/mVYD4urKmeqE.mp3?t=1789906482
- Host voice: preset `voice_1787`-style input; guest voice likewise (two distinct voices).
- 1 MP3 part(s) staged as `.b64` under `.staging/thomas-baigneres-olvid-concurrencer-whatsapp-san/`; decode and concatenate in filename order:

```
for f in .staging/thomas-baigneres-olvid-concurrencer-whatsapp-san/*.b64; do base64 -d "$f"; done > thomas-baigneres-olvid-concurrencer-whatsapp-san-en.mp3
```
