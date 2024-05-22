# Podly Pure Podcasts

Ad-block for podcasts. Create a private ad-free RSS feed.

Podly will:

- download the requested episode
- transcribe the episode
- have Chat GPT label ad segments
- remove the ad segements
- deliver the ad-free version of the podcast to you

# Usage

- Start the server & note the URL.
  - For example, `192.168.0.2:5001`
  - It'll try to register an mDNS record at `podly.local`
- Open a podcast app & subscribe to a podcast by appending the RSS to the 'rss' endpoint.
  - For example, to subscribe to `https://mypodcast.com/rss.xml`
  - Subscribe to `http://podly.local:5001/rss/https://mypodcast.com/rss.xml`
- Select an episode & download
- Wait patiently :)

# How To Run

Copy `.env.example` into new file `.env`. Update `OPENAI_API_KEY` with your key.

```
pipenv --python 3.11
pipenv install
pipenv shell
python src/main.py
```
