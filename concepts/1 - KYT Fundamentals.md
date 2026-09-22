

# KYT fundamentals

## 1. KYC, KYB, and KYT - The Core Distinction

> **KYT is not a binary clean/dirty classifier. A professional system combines identity context, blockchain intelligence, exposure, behavior, rules, and possibly machine learning to produce explainable risk information for downstream policy and human review.**

KYC, KYB, and KYT solve related but different compliance and risk problems. The first two establish who a customer or business is; KYT continuously evaluates what money and blockchain transactions are doing.

<mark>KYC</mark> - Who is this person?  

<mark>KYB</mark> - Who is this company?  

<mark>KYT</mark> - What is the money doing?

```python
if a == "hello":
    print("hello")
```

### 1.1 KYC - Know Your Customer

KYC concerns the identity and risk profile of an individual. It answers whether the person is who they claim to be and establishes customer context that later helps interpret transaction behavior.

- Name

- Date of birth

- Identity document

- Country and residence

- Source of funds

- Occupation

- Customer risk classification

Typical questions include whether the identity is genuine, whether the customer is subject to sanctions, and whether the customer belongs to a higher-risk category that requires stronger controls.

### 1.2 KYB - Know Your Business

KYB applies similar principles to organizations. It establishes the legal identity, ownership, business purpose, and expected behavior of a company or other legal entity.

- Company identity and registration

- Jurisdiction

- Directors

- Beneficial owners

- Business activity

- Expected transaction behavior

Example: if a small software consulting company that normally handles modest payments suddenly begins moving very large stablecoin volumes every day, the blockchain activity alone shows volume, while KYB context shows that the activity may be inconsistent with the stated business model.

### 1.3 KYT - Know Your Transaction

KYT is continuous transaction monitoring and risk assessment. It examines what funds are doing on-chain, where funds come from, where they go, which counterparties are involved, and whether the behavior matches known risk patterns or customer context.

```text
CUSTOMER
|
KYC / KYB
|
v
WHO SHOULD THIS BE?
|
|
BLOCKCHAIN -----+------> KYT
ACTIVITY |
v
WHAT ARE THEY DOING?
|
v
COMBINED CONTEXT
```

> **KYC/KYB establishes identity and expected context. KYT evaluates actual transaction behavior and blockchain exposure. Professional systems need both.**

## 2. KYT as Crypto-Native Transaction Monitoring

Financial institutions monitored transactions long before cryptocurrency. Traditional transaction monitoring looks for behavior that deviates from normal customer activity, suspicious flow patterns, unusual counterparties, or other indicators. KYT extends this idea using public blockchain data and blockchain-specific intelligence.

Traditional example:  
Customer normally spends about \$3,000/month  

```text
Suddenly:
\$400,000 enters account
-> rapidly split into 20 transfers
-> sent internationally
```

Result: potentially unusual behavior that may require review.

Crypto adds a highly structured public ledger. A KYT engine may inspect sender, recipient, amount, asset, blockchain, historical activity, counterparties, fund-flow history, and known address or entity attribution.

### 2.1 High-level professional KYT pipeline

```text
TRANSACTION
|
v
Blockchain data
+
Customer data
+
Intelligence data
|
v
KYT ENGINE
+----------------+----------------+
| | |
v v v
Attribution Rules Behavior
| | |
+----------------+----------------+
|
v
Risk evaluation
|
v
Alert / result
|
+-----------+-----------+
v v v
allow review escalate
```

Later layers can include graph analysis, machine learning, Spark, data lakes, and feature stores. Those technologies support the pipeline; they do not change its business meaning.

## 3. Addresses, Wallets, Entities, Attribution, and Labels

The phrase "dirty wallet" is convenient shorthand but is too simplistic for engineering a professional risk system. Risk is multi-dimensional and depends on exposure, behavior, context, evidence, confidence, severity, and policy.

```text
Wallet A
direct sanctions exposure
-> extremely serious
```

```text
Wallet B
received a small fraction of funds through an address
that interacted with a mixer three hops ago
-> context-dependent risk
```

```text
Wallet C
no known illicit counterparty, but behavior resembles laundering
-> behavioral risk
```

```text
Wallet D
interacts with an entity prohibited by company policy
-> policy risk
```

> **A blockchain address is not inherently "clean" or "dirty." Professional KYT evaluates risk category, severity, reasons, exposure, confidence, behavior, and context.**

### 3.1 Address vs wallet vs entity

| **Concept** | **Meaning**                                                                                                                       |
|-------------|-----------------------------------------------------------------------------------------------------------------------------------|
| Address     | A blockchain identifier, such as an Ethereum or Bitcoin address.                                                                  |
| Wallet      | A user-facing wallet or an analytical grouping of one or more addresses believed to be controlled together, depending on context. |
| Entity      | The real-world person, organization, service, or illicit actor believed to control one or more addresses.                         |

```text
Address 1 --\
Address 2 ----+--> Exchange / service / entity
Address 3 --/
```

### 3.2 Wallet attribution

Wallet attribution links blockchain addresses or clusters to real-world entities using on-chain analysis together with off-chain evidence. Attribution transforms raw ledger activity into information that compliance and risk systems can reason about.

```text
Raw blockchain:
0xABC -> 0xDEF
```

```text
Attributed blockchain:
Customer wallet -> Known exchange
```

or  

```text
Customer wallet -> Ransomware-associated cluster
```

The attributed version is far more useful because the system can reason about the type and risk of the counterparty rather than only hexadecimal addresses.

### 3.3 Where labels come from

Professional blockchain-intelligence companies combine many evidence sources. Possible sources include:

- Public blockchain behavior and transaction patterns

- Publicly disclosed addresses

- Sanctions lists

- Law-enforcement information

- Open-source intelligence

- Service disclosures and known deposit addresses

- Investigative research and controlled transactions

- Clustering heuristics

- Other proprietary intelligence

Not every attribution has equal certainty. A well-designed system records the source, supporting evidence, confidence, and timestamp associated with an attribution.

> **Explainability starts at attribution. Risk systems should preserve why an address or entity received a label, how confident the system is, and when that conclusion was established.**

## 4. Sanctions Intelligence and Time-Aware Attribution

Sanctions authorities can publish digital-currency addresses directly in sanctions-list entries. KYT systems therefore commonly ingest authoritative sanctions intelligence and compare transaction counterparties against current lists.

KYT intelligence table  

### address category  
0xABC sanctioned  
0xDEF ransomware  
bc1XYZ darknet service  
0x987 exchange

```text
Customer
|
| sends funds
v
0xABC
|
v
SANCTIONS MATCH
```

A direct sanctions match is typically a very strong risk signal. However, intelligence changes over time: addresses can be added, updated, removed, or reclassified. Production KYT therefore needs time-aware and versioned intelligence rather than a static list downloaded once.

> **Risk intelligence is time-sensitive. Historical transactions may need to be re-evaluated when sanctions, labels, attribution, or other intelligence changes.**

## 5. Direct and Indirect Exposure

### 5.1 Direct exposure

Direct exposure occurs when the monitored address transacts immediately with a known risky source or destination.

```text
Known ransomware wallet
|
| 10 ETH
v
Customer
```

Direct incoming exposure

```text
Customer
|
| 100 USDC
v
Sanctioned service
```

Direct outgoing exposure

### 5.2 Indirect exposure

Indirect exposure exists when the connection to the risky entity passes through intermediary addresses or services.

```text
Known ransomware
|
v
Wallet X
|
v
Wallet Y
|
v
Customer
```

Indirect exposure

Indirect exposure can be described in hops: one hop, two hops, three hops, and so on. Modern commercial systems may trace through intermediaries until a known service or entity is reached.

### 5.3 Direct and indirect exposure are not equivalent

```text
Case A:
Ransomware -> Customer
```

```text
Case B:
Ransomware -> Wallet 1 -> Wallet 2 -> Wallet 3 -> Large exchange -> Customer
```

Treating these situations identically would be simplistic. Risk interpretation depends on distance, context, intermediary type, direction, amount, percentage exposure, recency, and organization policy.

> **Direct and indirect exposure are different risk signals. Indirect exposure becomes increasingly context-dependent as funds pass through intermediaries.**

### 5.4 Exposure amount and percentage

Absolute amount and proportional exposure both matter. A wallet that received \$100 of remotely risky funds within \$1,000,000 of legitimate activity is not equivalent to a wallet where \$800,000 of \$1,000,000 came directly from a ransomware-related source.

- Absolute exposed amount

- Percentage of total funds exposed

- Risk category

- Number of hops

- Direction of flow

- Transaction recency

### 5.5 Incoming vs outgoing exposure

```text
Incoming:
Risky service -> Customer
Question: where are the customer's funds coming from?
```

```text
Outgoing:
Customer -> Risky service
Question: where are the funds going?
```

Direction can later become an explicit feature, such as incoming_illicit_ratio or outgoing_illicit_ratio.

# 6. Behavioral Risk Signals

Known bad counterparties are only one source of KYT risk. A wallet can show suspicious behavior even when no counterparty has already been labelled illicit. Behavioral monitoring looks for unusual timing, amounts, velocity, flow structure, and interaction patterns.

- Rapid movement of funds

- Unusual transaction velocity

- Layering

- Structuring

- Chain hopping

- Many newly created counterparties

- Immediate forwarding of received funds

- Large deviation from the customer's normal behavior

- Interaction with mixers or privacy-enhancing services

## 6.1 Transaction velocity

Normal pattern:  
1-5 transfers per week  

Sudden behavior:  
200 transfers within 20 minutes  

Result: a potentially important behavioral signal.

Unusual velocity is not proof of wrongdoing. It is an observation that can raise risk depending on context and other signals.

> **Signal does not equal guilt. KYT produces evidence and indicators; downstream policy and human review interpret them.**

## 6.2 Structuring

Structuring is a pattern in which transactions are deliberately split or shaped to avoid thresholds or controls. The exact legal definition varies, but the engineering lesson is that transaction sequences may be suspicious even when each individual transfer appears ordinary.

Example threshold: \$10,000  

Observed sequence:  
\$9,900  
\$9,800  
\$9,700  
\$9,600  

The pattern may matter more than any single transaction.

## 6.3 Layering

```text
Illicit funds
|
v
Wallet A
|
v
Wallet B
|
v
Bridge
|
v
Wallet C
|
v
DEX
|
v
Wallet D
|
v
Exchange
```

Layering broadly refers to moving funds through multiple steps, services, or assets in ways that obscure their origin or ownership. A single transfer may look harmless while the full path becomes informative.

## 6.4 Cross-chain obfuscation

```text
Ethereum
|
v
Bridge
|
v
Arbitrum
|
v
DEX
|
v
Solana
```

Cross-chain movement can be part of legitimate activity or an attempt to make tracing harder. For a bridge company, bridge use itself cannot be treated as suspicious; context, source, destination, timing, and behavior determine its risk significance.

> **Bridge usage is not inherently suspicious. It is a feature whose meaning depends on source, destination, flow pattern, and broader transaction context.**

## 6.5 Mixers

Mixers are services designed to make the flow of funds harder to trace by pooling, combining, or obscuring transaction paths. Exposure to mixer-type services can be a risk signal, but mixer interaction alone is not proof of criminal activity. Treatment depends on policy, jurisdiction, context, and exposure.

# 7. Risk-Based Compliance, Unhosted Wallets, and Policy Context

The risk-based approach means organizations identify different levels and types of risk and apply controls proportionately. It does not mean treating every customer or transaction identically.

```text
LOW RISK
-> normal processing
```

```text
MEDIUM RISK
-> additional review
```

```text
HIGH RISK
-> enhanced review / restriction / escalation
```

Exact actions and thresholds depend on jurisdiction, regulation, business model, and internal compliance policy.

## 7.1 Unhosted wallets

An unhosted or self-custody wallet is generally controlled directly by its user rather than through a regulated custodian. The important point for KYT is that less verified identity context may be available for an arbitrary self-custody address than for an account at a regulated intermediary.

```text
Self-custody context:
Customer -> MetaMask / hardware wallet
```

```text
Custodial context:
Customer -> regulated exchange account
```

A regulated exchange account may provide additional context such as verified customer identity, institution, and jurisdiction. An unhosted wallet is not inherently illicit; it is simply a context with different information and risk characteristics.

## 7.2 Risk appetite

Different organizations tolerate different categories and levels of risk. A conservative bank, a crypto-native exchange, and a bridge infrastructure provider may configure different thresholds, prohibited categories, indirect exposure sensitivities, and manual-review procedures.

> **The KYT engine produces intelligence. Company policy defines how that intelligence affects transactions and customers.**

# 8. Signals, Rules, Machine Learning, Scores, Alerts, Severity, and Confidence

## 8.1 Risk signal vs rule

A signal is observed information. A rule is logic that interprets one or more signals.

Signals:  
direct_ransomware_exposure = 3%  
transaction_count_last_hour = 84  
customer_country = X  
wallet_age = 2 days  

Rule:  
IF direct ransomware exposure \> 0  
THEN raise HIGH severity alert

Another rule:  
IF transaction_velocity \> threshold  
AND wallet_age \< 24h  
THEN raise behavioral alert

> **Signal = observation. Rule = policy or deterministic logic applied to observations.**

## 8.2 Rule engine

```text
Transaction
|
v
Sanctions rule
|
v
Direct exposure rule
|
v
Indirect exposure rule
|
v
Velocity rule
|
v
Volume rule
|
v
Risk result
```

This architecture connects naturally to the Chain of Responsibility pattern from backend design. In Go, each rule can implement a common interface and the engine can evaluate a sequence of independent checks.

```go
type RiskRule interface {
	Evaluate(ctx context.Context, tx Transaction) Result
}
```

Implementations:  
- SanctionsRule  
- DirectExposureRule  
- VelocityRule  
- MixerExposureRule

## 8.3 Rule vs machine learning

| **Approach** | **Meaning**                                              | **Good for**                                                                                       |
|--------------|----------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Rule         | Human-defined deterministic logic.                       | Sanctions, known illicit counterparties, hard policy constraints, thresholds, known typologies.    |
| ML model     | Statistical relationship learned from labelled examples. | Complex behavioral combinations, probabilistic classification, patterns that rigid rules may miss. |

Example rule: if an address is on a current sanctions list, raise a severe alert. Example ML output: using transaction frequency, volume, graph relationships, wallet age, and other features, estimate P(illicit) = 0.73.

A deterministic sanctions match should not be delegated to a statistical model. Conversely, a previously unknown address may still exhibit suspicious combinations of behaviors that an ML model can identify.

> **Mature KYT systems often combine intelligence + deterministic rules + behavioral analysis + machine learning. Neither rules nor ML replaces the other.**

## 8.4 Risk score

There is no universal industry formula in which a score such as 82 has the same meaning everywhere. Vendors and institutions may use 0-100 scores, 0-10 scores, categorical risk levels, alerts, or combinations of these.

```text
Inputs
|- exposure
|- labels
|- rules
|- behavior
|- ML
`- customer context
|
v
RISK RESULT
```

A risk score is therefore an implementation and policy mechanism rather than a universal mathematical truth.

## 8.5 Risk score vs risk level

A numerical score can be mapped to a human-readable level. Example educational thresholds:

| **Score** | **Level** |
|-----------|-----------|
| 0-29      | LOW       |
| 30-59     | MEDIUM    |
| 60-79     | HIGH      |
| 80-100    | CRITICAL  |

These thresholds are demonstration values only. Real thresholds must be defined by the organization and its compliance policy.

## 8.6 Risk score vs alert

A score is an overall assessment; an alert identifies a specific condition that deserves attention.

risk_score = 84  

alerts:  
- sanctions-related counterparty  
- rapid transaction velocity  
- high one-hop exposure

## 8.7 Severity

Alert severity may depend on risk category, transaction amount, direct vs indirect exposure, transaction direction, business policy, and other context.

LOW  
MEDIUM  
HIGH  
SEVERE

## 8.8 Risk vs confidence

Risk and confidence are separate dimensions. A category can be very severe if the attribution is correct while the attribution itself may have limited confidence.

RISK  
How serious is the activity or category?  

CONFIDENCE  
How certain are we about the evidence, attribution, or classification?

An educational API can optionally expose both risk and confidence, but confidence should not be confused with risk severity.

# 9. Explainability, Human Review, Case Management, and Model Quality

## 9.1 Explainability

Weak result:  
risk = 91  

Question: why?  
Answer: unknown

Better result:  
risk_score: 91  
reasons:  
- 22% direct exposure to sanctioned entity  
- received funds from ransomware cluster  
- transaction velocity 9x customer baseline  
- ML illicit probability 0.76

Explainability supports human review, audits, debugging, regulatory examination, customer disputes, false-positive analysis, and model improvement. Risk systems should produce evidence, not mysterious numbers.

> **A good KYT result should include score or level, severity, reasons, exposure evidence, model/rule context, and enough metadata to reproduce or investigate the decision.**

## 9.2 Alert does not equal block

KYT detects and informs. A separate policy or workflow determines what happens after a risk result.

- Allow

- Continue monitoring

- Manual review

- Request more information

- Delay

- Escalate

- Restrict

- Reject

- Report

The exact action is a business and compliance decision. It should not be invented autonomously by a machine-learning model.

## 9.3 Human-in-the-loop review

When the system generates a higher-risk result, an analyst may inspect customer KYC/KYB, transaction history, graph relationships, counterparties, business purpose, source of funds, previous alerts, and additional intelligence before deciding whether the alert is a false positive, a valid concern, or requires more investigation.

> **KYT is primarily a decision-support system. A high score is not the same as proving criminal conduct.**

## 9.4 Case management

```text
ALERT CREATED
|
v
UNASSIGNED
|
v
UNDER REVIEW
|
+----> CLOSED - FALSE POSITIVE
|
+----> ESCALATED
|
`----> CUSTOMER INFORMATION REQUEST
```

Analysts may attach notes, evidence, documents, decisions, and decision reasons. This is naturally modelled as a state machine, connecting KYT to the backend architecture concepts already studied.

## 9.5 Suspicious activity reporting

Depending on jurisdiction and institution, sufficiently suspicious activity may result in formal reporting such as a SAR or STR. The engineering flow to understand is:

```text
KYT signal
|
v
Alert
|
v
Analyst investigation
|
v
Decision
|
v
possible regulatory report
```

The key principle is that an ML score should not automatically accuse a customer of a crime or file a report without the appropriate compliance workflow.

## 9.6 False positives

A false positive is legitimate or acceptable activity that the system incorrectly flags as suspicious. Excessive false positives can overwhelm compliance teams, increase customer friction, and cause analysts to miss genuinely important cases.

```text
100,000 alerts/day
|
v
only a tiny fraction actually matter
|
v
compliance team overwhelmed
```

Reducing false positives requires good attribution, sensible thresholds, customer context, behavioral baselines, rule tuning, and alert prioritization.

## 9.7 False negatives

A false negative occurs when the system rates activity as low risk even though it is actually suspicious or illicit. Detection systems therefore balance the cost of false positives against the danger of missed activity.

```text
Higher sensitivity
-> catch more suspicious activity
-> usually more false positives
```

```text
Lower sensitivity
-> fewer alerts
-> potentially more missed activity
```

Later, precision and recall will give formal ML metrics for this tradeoff.

# 10. Time and Direction in KYT

## 10.1 Risk changes over time

January 1  
Address 0xABC appears harmless.  

January 10  
Customer sends funds to 0xABC.  

February 15  
New intelligence determines 0xABC belongs to a darknet service.  

The January transaction now has new risk context.

This is why a professional KYT system may need to re-evaluate historical activity when intelligence changes. Historical transaction data must remain available for retrospective analysis.

## 10.2 Real-time vs retrospective monitoring

```text
REAL-TIME
transaction happens
|
v
score immediately
|
v
allow / hold / review
```

```text
RETROSPECTIVE
new intelligence arrives
|
v
rescan historical activity
|
v
identify past exposure
|
v
new alert
```

Both modes are important. Real-time monitoring affects current transactions; retrospective monitoring finds risk that becomes visible only after new information is discovered.

## 10.3 Pre-transaction vs post-transaction screening

```text
PRE-TRANSACTION
Customer requests withdrawal
|
v
screen destination
|
v
risk decision
|
v
broadcast or stop
```

```text
POST-TRANSACTION
deposit arrives
|
v
analyze source
|
v
alert if risky
```

A payments or bridge infrastructure company can need both incoming-deposit KYT and outgoing-destination screening.

# 11. Stridge-Style KYT Integration

The following is an educational architecture aligned with a cross-chain payment backend. It is not a claim about Stridge's private production implementation or internal compliance policy.

```text
Customer sends USDC
|
v
Deposit Address
|
v
Blockchain Observer
|
v
DepositConfirmed
|
v
KYT Service
|
|- Who sent it?
|- Known label?
|- Sanctions match?
|- Direct exposure?
|- Indirect exposure?
|- Suspicious behavior?
`- Customer context?
|
v
RESULT
```

```json
{
"risk_score": 76,
"level": "high",
"alerts": [
"direct exposure to high-risk service",
"unusual transaction velocity"
]
}
```

```text
Settlement workflow
|
|- low -> continue
|- medium -> policy-dependent review
`- high -> hold / review / escalate
```

Those actions are examples only. Real production actions and thresholds are defined by compliance policy, jurisdiction, and company risk appetite.

## 11.1 Information a KYT engine consumes

| **Category**     | **Examples**                                                                           |
|------------------|----------------------------------------------------------------------------------------|
| Transaction data | Transaction hash, chain, block/time, sender, receiver, asset, amount.                  |
| Attribution data | Known entity, entity type, risk category, attribution confidence.                      |
| Exposure data    | Direct/indirect counterparties, hops, amounts, percentage exposure.                    |
| Behavioral data  | History, frequency, velocity, volume, timing, counterparty diversity.                  |
| Customer data    | KYC/KYB profile, country, business type, expected behavior, previous alerts.           |
| Intelligence     | Sanctions, scams, ransomware, hacks, darknet, mixers, fraud, other high-risk services. |

## 11.2 Professional result structure

Avoid designing the eventual API as a Boolean such as {"dirty": true} or as an unexplained number. The direction should be an explainable, versioned risk result with evidence.

```json
{
"address": "0xABC...",
"risk_score": 89,
"risk_level": "critical",
"confidence": 0.92,
"reasons": [
"direct sanctions exposure",
"high-risk counterparty interaction",
"abnormal transaction velocity"
],
"exposures": [
{
"category": "sanctions",
"type": "direct",
"amount_usd": 12000
}
],
"model_version": "risk-v4",
"evaluated_at": "..."
}
```

The capstone can use a simpler schema, but the professional direction is to return evidence, not an opaque score.

## 11.3 What should not determine risk alone

- A large transaction does not automatically imply criminal activity.

- A new wallet does not automatically imply criminal activity.

- Using a bridge does not automatically imply criminal activity.

- Mixer exposure does not automatically prove criminal activity.

- One ML prediction should not automatically decide that a customer is criminal.

These are features or signals whose meaning depends on the broader evidence and context.

## 11.4 Complete Day 1 business architecture

```text
CUSTOMER
|
KYC / KYB
|
v
CUSTOMER CONTEXT
|
|
v
```

```text
BLOCKCHAIN --------> TRANSACTION
|
v
BLOCKCHAIN DATA
|
+--------------+--------------+
| | |
v v v
Attribution Exposure Behavior
| | |
+--------------+--------------+
|
v
KYT ENGINE
|
+----------+-----------+
| | |
v v v
Rules ML Intelligence
| | |
+----------+-----------+
|
v
RISK RESULT
|
score + reasons + alerts
|
v
POLICY ENGINE
|
+--------------+--------------+
v v v
ALLOW REVIEW ESCALATE
|
v
ANALYST
|
case / investigation
|
v
eventual feedback
```

Later stages extend the data side with Kafka, a data lake, Spark, feature generation, and ML training. The business meaning of the pipeline remains the same.

# 12. Key Distinctions and Critical Principles

| **Distinction**             | **Correct mental model**                                                                                                 |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------------|
| KYC vs KYT                  | KYC establishes identity; KYT evaluates transaction behavior and risk.                                                   |
| Address vs Entity           | An address is a blockchain identifier; an entity is a real-world actor or service associated with one or more addresses. |
| Direct vs Indirect Exposure | Direct exposure is an immediate risky counterparty; indirect exposure connects through intermediaries.                   |
| Signal vs Rule              | A signal is observed information; a rule interprets signals using deterministic policy logic.                            |
| Rule vs ML                  | Rules are human-defined deterministic logic; ML learns statistical relationships from labelled data.                     |
| Score vs Alert              | A score is an overall assessment; an alert identifies a specific condition requiring attention.                          |
| Risk vs Confidence          | Risk describes seriousness; confidence describes certainty in the evidence or classification.                            |

## 12.1 Critical statements

> **KYT is continuous transaction-risk monitoring; KYC/KYB establish who the customer or business is.**
>
> **A blockchain address is not inherently "clean" or "dirty"; professional systems evaluate exposure, behavior, intelligence, context, and confidence.**
>
> **Direct and indirect exposure are different risk signals, and indirect exposure becomes increasingly context-dependent across intermediaries.**
>
> **A suspicious signal or ML prediction is evidence for a risk decision, not proof that a customer committed a crime.**
>
> **KYT should produce explainable results - score, severity, reasons, and exposure - not just an opaque number.**
>
> **The risk engine provides intelligence; policy and human compliance workflows determine the resulting action.**

## 12.2 What to skip today

Do not spend Day 1 on the following topics. They are either covered later in the one-week roadmap or outside the current engineering objective:

- Graph algorithms

- Address-clustering algorithms

- Elliptic++

- Spark and PySpark

- Data-lake implementation

- Random Forest

- Logistic Regression

- Graph neural networks

- Feature engineering

- Precision and recall

- Kafka KYT implementation

- Go KYT service implementation

- OFAC regulations in depth

- Travel Rule implementation

- SAR filing rules

- Country-specific AML law

## 12.3 Optional original-source reading

The lesson is self-contained. Two short vendor overviews are useful only for seeing how major commercial providers describe the same ideas and terminology.

**Chainalysis - Know Your Transaction:** https://www.chainalysis.com/glossary/know-your-transaction/

**TRM Labs - Know Your Transaction (KYT):** https://www.trmlabs.com/glossary/know-your-transaction-kyt

FATF guidance is important background for compliance policy, but reading the full regulatory guidance is not necessary for this engineering sprint.

## 12.4 Primary references

**Chainalysis - KYT and transaction monitoring:** https://www.chainalysis.com/product/kyt/

**Chainalysis - Transaction Monitoring:** https://www.chainalysis.com/glossary/transaction-monitoring/

**Chainalysis - Wallet Attribution:** https://www.chainalysis.com/glossary/wallet-attribution/

**TRM Labs - Know Your Transaction:** https://www.trmlabs.com/glossary/know-your-transaction-kyt

**TRM Labs - Glass Box Attribution:** https://www.trmlabs.com/glossary/glass-box-attribution

**FATF - Virtual Assets:** https://www.fatf-gafi.org/en/topics/virtual-assets.html

**OFAC - Digital Currency Addresses FAQ:** https://ofac.treasury.gov/faqs/topic/1626

## 12.5 Day 1 oral exam

1.  What is KYC?

2.  What is KYB?

3.  What is KYT?

4.  Why does a company need both KYC/KYB and KYT?

5.  What is wallet attribution?

6.  Where might wallet labels come from?

7.  Address vs wallet vs entity?

8.  What is direct exposure?

9.  What is indirect exposure?

10. Why should direct exposure and three-hop indirect exposure not automatically have identical risk?

11. Why does exposure percentage matter?

12. Why does transaction direction matter?

13. Give five suspicious behavioral signals that do not require a known illicit address.

14. What is structuring?

15. What is layering?

16. Why is bridge usage not inherently suspicious?

17. What is a risk-based approach?

18. What is an unhosted wallet, and why might it require different context?

19. Signal vs rule?

20. Rule engine vs ML model?

21. Why would sanctions detection usually be a deterministic rule rather than ML?

22. Why might ML find something rules do not?

23. Is there a universal KYT 0-100 risk-score formula?

24. Risk score vs risk level?

25. Risk score vs alert?

26. What might determine alert severity?

27. Risk vs confidence?

28. Why does explainability matter?

29. Why should a high-risk alert not automatically equal "criminal"?

30. What is human-in-the-loop review?

31. What is case management?

32. What is a false positive?

33. What is a false negative?

34. What is risk appetite?

35. Why can the risk of a historical transaction change later?

36. Real-time vs retrospective monitoring?

37. Pre-transaction vs post-transaction screening?

38. What data should a KYT engine consume?

39. What should a good KYT response contain besides a score?

40. Walk through a Stridge-like deposit from DepositConfirmed to KYT result to settlement policy.

> **Day 1 completion target: answer at least 32 of 40 questions cleanly without notes. Then move to blockchain transaction graphs, address/entity labels, N-hop exposure, and graph features.**
