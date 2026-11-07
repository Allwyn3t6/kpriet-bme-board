# BME Board – KPRIET Biomedical Engineering

A public, auto-updating notice board for the Department of Biomedical Engineering, KPR Institute of Engineering and Technology, Coimbatore. It shows:

- **Thought for the day**: one quote a day (Thirukkural, Dr. A. P. J. Abdul Kalam, Swami Vivekananda and others).
- **KPRIET live**: announcements and Stories from [kpriet.ac.in](https://www.kpriet.ac.in/).
- **Coming up at KPRIET**: upcoming events, with countdowns.
- **Around Coimbatore**: headlines from the public Coimbatore feeds of The Hindu and Times of India. Crime and accident news is filtered out, and every headline links to its publisher.

GitHub Actions rebuilds the board every hour (`.github/workflows/board.yml`). If a source is unreachable, the last good data is kept.

**Privacy:** this repository and site contain public information only. The department's internal academic-operations app, with its staff, student and task data, is separate and private.

To edit the quotes or news filters, change `home_feeds.json` and commit. The board rebuilds automatically.
