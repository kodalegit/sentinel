**Project Proposal: Sentinel**

**Track:** Governance & Public Policy  
**Theme:** AI for National Prosperity

**Proposed By:** Victor Kimani

**1\. Problem Statement**

Public procurement, the process by which governments purchase goods and services, is the backbone of national development. It accounts for a significant percentage of the national GDP, funding everything from critical infrastructure and healthcare supplies to defence systems. However, it is also the domain most vulnerable to corruption, inefficiency, and organised crime.

Currently, the oversight of these tenders is fraught with systemic weaknesses. Government auditors and civil society watchdogs are overwhelmed by the sheer volume of unstructured data (PDFs, scanned images, and disconnected databases). Audits are typically "post-mortem," conducted months or years after funds have been stolen or misused.

The specific challenges include:

- **Bid Rigging & Cartels:** "Shell companies" often rotate wins among themselves to maintain artificially high prices, a pattern invisible to human auditors looking at single contracts in isolation.
- **Conflict of Interest:** Contracts are frequently awarded to entities secretly owned by public officials or their relatives, hidden behind complex corporate structures.
- **Anomalous Pricing:** Goods are procured at vastly inflated rates (e.g., the infamous "wheelbarrow scandals" or overpriced medical kits), draining the treasury.

The inability to detect these threats in real-time directly undermines **National Prosperity**. Every shilling lost to procurement fraud is a shilling stolen from education, healthcare, and national security. Without a technological intervention to enforce transparency and predict risk, the nation remains vulnerable to economic haemorrhage and the erosion of public trust.

**2\. Proposed Solution**

**Sentinel** is an AI-powered "Public Procurement Guardian." It is a real-time auditing platform that transforms opaque procurement data into actionable intelligence. By leveraging Graph Analytics and Anomaly Detection, Sentinel automates the identification of high-risk tenders before the contract is finalised.

Our solution moves governance from **reactive auditing** to **proactive prevention**.

**Core Functionality**

Sentinel operates on a three-stage pipeline designed for the "Governance & Public Policy" track:

**1\. The Ingestion & Structuring Engine**  
Government data is often locked in non-machine-readable formats. Sentinel allows users (auditors/public officers) to upload tender documents (PDFs, Excel) or scrape public portals. It uses OCR and Natural Language Processing (NLP) to extract critical entities:

- Vendor Names and Directors.
- Item descriptions and Unit Prices.
- Dates (Bid submission vs. Deadline).

**2\. The "Shadow Graph" (Network Analysis)**  
Sentinel constructs a Knowledge Graph where nodes represent _Companies_, _Directors_, _Public Officials_, and _Tenders_.

- **Conflict Detection:** The system traverses the graph to find paths between a winning vendor and the awarding official (e.g., "Official A is the brother of Director B").
- **Cluster Detection:** It identifies "Supplier Cartels"-groups of companies that always bid on the same tenders but take turns winning, or companies that share the same physical address and phone number.

**3\. The Anomaly Detector (Predictive Analytics)**  
Using statistical modelling and unsupervised Machine Learning, Sentinel assigns a **"Risk Score" (0-100)** to every tender based on:

- **Price Deviation:** Comparing unit prices against market rates or historical averages.
- **Timing Anomalies:** Flagging bids submitted minutes before a deadline or tenders with unusually short application windows designed to exclude competition.
- **Vendor History:** Flagging companies created only days before a multi-million shilling tender.

**The MVP Experience**

For the hackathon, we will build a functional Minimum Viable Product demonstrating this flow:

- **The Dashboard:** A Next.js web interface where an "Auditor" can view a feed of recent tenders.
- **Risk Heatmap:** Tenders are colour-coded (Red/Yellow/Green). Clicking a "Red" tender reveals the _Why_: _"High Risk: Vendor shares director with 3 losing bidders."_
- **Graph Visualisation:** An interactive node-link diagram allowing the user to visually explore the connections between a suspicious company and other entities.

By automating the heavy lifting of data linkage, Sentinel empowers policymakers to make evidence-based decisions, freeze suspicious payments immediately, and ensure tax revenues are channeled toward genuine national development.

**3\. Technology & Methodology**

We have designed Sentinel to be deployable, scalable, and modular.

**Tech Stack**

- **Frontend:** **Next.js (TypeScript)**. This ensures a responsive, modern, and type-safe user interface. We will use **Tailwind CSS** for rapid UI development and **Recharts** or **React Force Graph** to visualise the corruption networks.
- **Backend:** **FastAPI (Python)**. Chosen for its high performance and native support for asynchronous processing, which is crucial when handling data-heavy AI tasks.
- **Database:** **PostgreSQL** to store structured tender data and relationships.

**AI & Data Libraries (Python Ecosystem)**

- **Data Processing:** Pandas and NumPy for cleaning and structuring tabular data.
- **Graph Analytics:** NetworkX. We will use this to build the entity graphs and calculate centrality measures (identifying key influencers in a corruption network).
- **Anomaly Detection:** Scikit-learn. Specifically, we will implement the **Isolation Forest** algorithm, which is excellent for detecting outliers in high-dimensional datasets (identifying tenders that "don't look right").
- **Text Extraction:** PyPDF2 or Tesseract (via wrapper) to parse unstructured tender documents.

**Methodology**

- **Data Simulation:** As real-time government data may be restricted, we will generate a synthetic dataset (based on the Open Contracting Data Standard) seeded with known "fraud patterns" (e.g., inflated prices, cross-linked directors) to prove the model works.
- **Graph Construction:** We will map the synthetic data into nodes (People/Companies) and edges (Ownership/Transactions).
- **Scoring Logic:** The backend will compute a weighted average of the _Graph Risk_ (connections) and _Statistical Risk_ (price/timing) to output the final Trust Score.

**4\. Relevance to Theme**

**Sentinel** aligns perfectly with the theme **"AI for National Prosperity: Leveraging Innovation for Sustainable Development and Security."**

**1\. Strengthening Governance (The Track Goal):**  
The brief specifically asks for solutions that "apply AI to strengthen governance through transparent decision-making." Sentinel acts as an unbiased digital auditor. By illuminating the dark corners of public procurement, it enforces transparency. It removes human discretion from the initial vetting process, reducing the window for bribery and corruption.

**2\. Economic Security as National Security:**  
Corruption is not just a financial crime; it is a security threat. Organised crime syndicates often use public contracts to launder money. By integrating the "Organised Crime" detection aspect, mapping networks of shell companies, Sentinel directly combats the financial engines that fund instability.

**3\. Sustainable Development:**  
Prosperity is impossible if funds allocated for development are diverted. If a nation allocates \$10M for a dam, but \$4M is lost to bid-rigging, the dam is never built, and the region suffers. Sentinel ensures that development funds achieve their intended impact. It creates a "Trust Loop": efficient spending leads to better services, which leads to increased citizen trust and national stability.

Sentinel is not just a tool for finding bad actors; it is a platform for securing the financial future of the nation.
