# AQ26 SerpAPI quota guard

You have `SERPAPI_API_KEY` with 250 free searches/month.

WeeklyV2 should keep SerpAPI low-volume:
- max 4 SerpAPI requests/run
- weekly schedule ≈ 16-20 searches/month
- stop on 401/403/429
- use only targeted official/regulatory discovery queries
- do not use SerpAPI as general news scraping

The current all-keys patch already references `SERPAPI_API_KEY`. This small patch adds a safe quota policy snippet that can be merged into `configs/aq26_weekly_v2_sources.yml`.
