Primary tools: Python (pandas, numpy, scipy, matplotlib, seaborn), SQL (DuckDB), Monte Carlo simulation, Jupyter, pytest, GitHub Actions, HTML/JS.

## Sports and media analytics

### [What is one race on the No. 44 worth?](nascar_sponsor_value)
A broadcast exposure model for part-time NASCAR sponsorships, built on all 36 races of the 2025 Cup Series (1,369 starts). It estimates the TV value a sponsor gets from one race on NY Racing's No. 44, prices in the risk of the car failing to qualify, and turns that into a pricing guide and a browser calculator. Key findings: a back-of-field start on FOX was worth about three times one on USA, FOX's window held about half of a backmarker's season value, and the Daytona 500, the most valuable race, is the one a part-time team can miss. The network effect is tested directly on the 36 races' Nielsen audiences: a regression controlling for track type puts a FOX race at 2.9× a USA race's audience (95% CI 1.9–4.5×).

*Monte Carlo simulation · regression with robust errors · calibration to published benchmarks · Bayesian qualification odds · DuckDB · data-quality tests · CI*
