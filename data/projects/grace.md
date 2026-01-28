# GRACE: Graph Reasoning with Adaptive Correlated Equilibrium

**Tags:** Project, Game Theory, RAG, Graph, Correlated Equilibrium, Control Theory, Reinforcement Learning

## Abstract

GRACE explores whether hallucinations in large language models can be reduced by controlling how inference is performed, rather than retraining the model itself. It treats retrieval, generation, and verification as a coordinated decision problem, but the analysis shows that the game-theoretic framing collapses into a centralized control system driven by noisy graph signals and risk-averse incentives. In practice, GRACE ends up being a useful lesson in why signal quality, uncertainty estimation, and evaluation matter more than equilibrium machinery when building reliable RAG.

## Some thoughts...

This project is from my graduate class. In that class, I first learn game theory, so this work is mainly an experiment to see if we can use game-theoretic control to make LLM pipeline more reliable and also more explainable. I do know game theory has been applied in Reinforcement Learning (RL), so when implementating this I did mistakenly imitate behaviors in RL and drift away from the original idea of game theory, but again it helps me understand game theory better. Plus, it kinda motivates me to look more into RL. After this project, I take an RL class in next semester to consolidate the missing parts.

---

## Overview

The main reason I come up with this idea is from a popular debate about why LLMs rarely say **"I don't know"**, but instead try to force an answer using whatever knowledge it has. This behavior is one of the direct causes of hallucination. A really good answer to this (in my opinion) is from this paper by OpenAI: [Why Language Models Hallucinate](https://arxiv.org/pdf/2509.04664). One big part of the reasons is due to stastical nature of current LLMs and their training process. Drawing on the paper, one key point leading to hallucination is in alignment, in which models are typically rewarded for correct answers but not penalized for incorrect ones. Under this incentive structure, it is rational for a model to always attempt an answer rather than abstain. If you think about it, this is similar to when we take a multiple choice exam with no penalty for wrong answers:

- Correct answer gives you +1 point
- Wrong answer gives you 0 penalty
- Then if you are uncertain, the rational strategy is still to guess, because expected value is positive:

$$
  \mathbb{E}[\text{score}] = p(\text{correct})\cdot 1 + (1-p(\text{correct}))\cdot 0 = p(\text{correct}) \ge 0.
$$

If you are allowed to “abstain” but abstain gives also 0, then guessing weakly dominates abstain.

For a graduate course project, I did not have sufficient time or resources to train a model from scratch or perform fine-tuning and alignment, so I tried a different angle to see if we can modify inference-time incentives by building an external decision layer around the model?

That is why I build GRACE. The basic idea is that Retrieval-Augmented Generation (RAG) is a static pipeline (retrieve → stuff into prompt → generate). But in reality, there will always be certain level of reasoning to get through a sequence of uncertainty to make a final decision.

- Should I trust retrieval evidence or skip it?
- Should I do shallow retrieval or deep multi-hop retrieval?
- Should I generate once or do self-consistency sampling?
- Should I pay extra cost to verify using an entailment model?
- When evidence is noisy, should I abstain instead of gambling?

If interested, you can read my [previous discussion about RAG and reasoning](?project=rag101.md#rag-reasoning).

Again, with that in mind, I try treating RAG pipeline as a **decision-making system under uncertainty** with the goal to make the _controller_ around the model more rational.

---

### Modeling the system as a cooperative game

I model the system as a cooperative game with three agents:

- **Retriever (R)**: decides retrieval depth, hop count, or early stopping.
- **Generator (G)**: decides whether to answer directly, use self-consistency, or abstain.
- **Verifier (V)**: decides whether to run verification and how strict it should be.

Each agent has a small discrete action space. All agents share the same objective, so this is a team game rather than a competitive one.

Instead of letting each agent act independently, I introduce a **mediator** that selects a joint action:

$$
a = (a_R, a_G, a_V).
$$

The mediator’s role is to coordinate decisions so that, for example, weak retrieval discourages aggressive generation, or expensive verification is only used when necessary. Now, if each agent optimizes locally, the system becomes unstable. For example, the generator may always answer because it does not directly pay the cost of retrieval or verification. To address this, I use the idea of a **correlated equilibrium (CE)**. A CE allows a mediator to recommend coordinated actions to all agents, such that no single agent benefits from deviating alone.

### State construction using retrieval graphs

A key question is how to define the state (s).

I build a graph from the retrieved documents, where nodes represent documents and edges represent semantic or citation relationships. From this subgraph, I compute simple structural signals, such as:

- node degree
- evidence diversity
- path coherence
- centrality (PageRank)
- redundancy or contradiction indicators

These signals are continuous, but I discretize them into a small finite state space. The purpose is not precision, but **risk estimation**: is the evidence strong, weak, noisy, or conflicting?

This state representation is external to the language model and does not rely on internal logits or hidden states.

### Utility design

All agents share a single utility function:

$$
U(s, a) = \mathbb{I}_{\text{correct}} \cdot R_{\text{correct}} + \mathbb{I}_{\text{abstain}} \cdot R_{\text{safe}} - \sum \text{Cost}
$$

The intuition is simple:

- Correct answers are rewarded.
- Abstention receives a smaller but positive reward.
- Computation (deep retrieval, verification) has a cost.
- Wrong answers lose opportunity value.

This utility structure changes the optimal behavior. When evidence quality is low, the expected utility of answering can become lower than the utility of abstaining.

### Learning the controller

The language model itself is frozen. What I learn is the mediator policy $\pi(a \mid s)$:

- State: discretized graph-based signals
- Action: joint action of retriever, generator, verifier
- Reward: utility defined above

This is conceptually similar to reinforcement learning, but the environment is the inference pipeline itself. The policy controls _how inference is performed_, not what tokens are generated.

### Why this reduces hallucination

Hallucination occurs when answering always dominates abstention. By modifying inference-time incentives, I create a regime where:

$$
\mathbb{E}[U(\text{answer})] < \mathbb{E}[U(\text{abstain})]
$$

under low-evidence states.

In this regime, saying “I don’t know” is not a failure. It is the rational equilibrium action.

---

## Problems

### Misapplication of Correlated Equilibrium to Team Problems

The core premise of GRACE was to model the Retriever, Generator, and Verifier as agents in a CE. I reasoned that a Mediator could coordinate their actions to avoid "hallucination risks". However, looking at my own definition of the game, I created a contradiction. If you notice, in the previous discussion, I said ["Modeling the system as a cooperative game"](#modeling-the-system-as-a-cooperative-game). By making agents **cooperative**, and operating under a "shared objective" to maximize a single global utility $U$, I unknowingly collapsed the game into a Marshak Team Problem. In a setting where every agent wants exactly the same outcome, the complex machinery of CE (designed to enforce obedience against self-interest) became redundant. There were no "competing interests" to mediate.

To elaborate more formally, in standard game theory, a Correlated Equilibrium is useful when:

- multiple agents act independently,
- each agent has its own utility function,
- and agents may benefit from deviating from a recommended action if it increases their private payoff.

The role of a Mediator in CE is to send correlated recommendations to agents in such a way that **no agent has an incentive to disobey**, assuming all others follow their recommendations. This requirement is formalized through **Incentive Compatibility (IC) constraints**, which ensure that unilateral deviation is never beneficial.

Formally, for agent $i$, the IC condition requires:

$$
\sum_{s_{-i}} P(s_{-i} \mid s_i)
\big[
u_i(s_i, s_{-i}) - u_i(s_i', s_{-i})
\big]
\ge 0
$$

This inequality states that, given the recommendation $s_i$, agent $i$ does not increase its expected utility by switching to an alternative action $s_i'$, assuming other agents follow their recommendations.

In GRACE, however, I explicitly defined the system such that **all agents share the exact same utility function**:

$$
u_i(s, a) = U_{\text{global}}(s, a)
\quad \text{for all } i
$$

Under this condition, the IC constraints lose their purpose. Since every agent values outcomes identically, there is no notion of private gain or deviation for self-interest. Any joint action that maximizes the global expected utility is automatically stable, because no agent can benefit by changing its behavior independently.

As a result:

- Any global optimum is trivially a Nash Equilibrium.
- Any Nash Equilibrium is trivially a Correlated Equilibrium.
- The Mediator has no strategic enforcement role to play.

In effect, I was applying equilibrium machinery designed for **strategic coordination** to a problem that was actually **centralized optimization**. The Mediator was not resolving conflicts between agents; it was simply computing:

$$
\vec{a}^* = \arg\max_{\vec{a}} \mathbb{E}[U(s, \vec{a})]
$$

This is a standard control or planning problem, not an equilibrium-finding problem.

Conceptually, I treated the system as if it required negotiation between self-interested parties, when in reality it was a single decision-maker choosing a configuration for its own internal components. The CE framing therefore added theoretical complexity without introducing additional explanatory or algorithmic power.

#### The "Mediator" was just a Bandit Policy

I described the Mediator as "orchestrating" the agents by consulting a policy table to "recommend" actions. I framed this as a **Quantal Response Equilibrium (QRE)** to handle noise.

$$
\pi(a|s) = \frac{\exp(\hat{Q}(s,a)/\tau)}{\sum_{a' \in A} \exp(\hat{Q}(s,a')/\tau)}
$$

Retrospectively, this is not QRE in the interactive sense. In QRE, Player A’s error model influences Player B’s strategy. In GRACE, there is no "Player A" or "Player B" making independent choices. There is only the Mediator selecting a joint tuple $\vec{a} = (a_R, a_G, a_V)$

Mathematically, this is simply a Contextual Bandit (or a single-step Markov Decision Process):

- Context ($S$): The discretized graph signals (Trust, Quality).
- Action ($A$): The joint pipeline configuration.
- Reward ($R$): Accuracy minus Cost.

I anthropomorphized the subroutines (Retriever, Generator) by calling them "players". In reality, they were just tools being executed by a central policy.

#### Incentive Cliff was a Control Theory Failure

The most revealing failure of GRACE was in its learned behavior. The utility function was designed to strongly penalize incorrect answers and reward safe abstention, with the intention that the system would learn a nuanced balance between answering and abstaining depending on evidence quality. Yet, it eventually turned out that the learned policy collapsed into extreme conservatism. Even in nominally “High Trust” states, variance in the graph-derived signals made answering appear too risky. As a result, abstention dominated most states.

This behavior was not a strategic equilibrium arising from agent interaction, but the direct consequence of optimizing a risk-averse objective under noisy state estimation. Because $Q(s,a)$ was estimated via Monte Carlo rollouts in a high-penalty environment, variance in reward estimates produced a bang–bang controller: whenever uncertainty was high, the optimal action snapped to abstention, regardless of nominal evidence strength.

Framing this problem as a game obscured the underlying cause. Had it been treated as a Bayesian decision problem, the primary focus would have been on reducing uncertainty in the state estimates rather than tuning equilibrium temperatures or interpreting the outcome as strategic caution.

Formally, the decision boundary implied by the utility is:

$$
\text{answer if } \Pr(\text{correct}\mid s,a)\cdot R_{\text{correct}} - \mathrm{Cost}(a) \ge R_{\text{safe}}
$$

Noisy or poorly calibrated state features depress estimates of $\Pr(\text{correct}\mid s,a)$, pushing the policy toward abstention even in states labeled as high confidence.

---

### Signal Problem

If the misuse of game-theoretic equilibrium was the first failure mode of GRACE, the second lies in the **signal processing pipeline** that feeds the Mediator. The Mediator’s decisions are entirely conditioned on a state $s$ derived from graph-theoretic signals. As in any control system, the quality of the controller is fundamentally bounded by the quality of its sensors. In GRACE, these sensors are mathematically ill-suited for the task they are expected to perform.

The signals attempt to summarize complex retrieval graphs into a small discrete state space. While this simplification is computationally convenient, it introduces severe information loss and systematic bias that the downstream policy cannot recover from.

#### Power Laws in PageRank-Based Trust Signals

The Trust signal $T$ is derived from the mean PageRank centrality $\rho$ of nodes reachable in the retrieved subgraph. However, it is a well-established result in network science that PageRank values in scale-free graphs follow a power-law (or Zipfian) distribution:

$$
P(\rho) \sim \rho^{-\gamma}, \quad \text{with } 2 < \gamma < 3
$$

In such distributions, probability mass is heavily concentrated near zero. The overwhelming majority of entities have near-zero PageRank, while a very small number of super-nodes (e.g., “United States”, “Water”, “Year”) dominate the upper tail.

GRACE discretizes this continuous signal using fixed thresholds (Low/Mid/High), then aggregates it into a meta-signal $T$ via addition with binned degree, and finally bins $T$ again into the final `Low/Mid/High` trust state. This two-stage discretization is problematic under heavy-tailed centrality distributions: static thresholds compress large dynamic ranges into the same bin, and the subsequent meta-aggregation further aliases distinct graph regimes. As a result, the final trust state discards scale information that can distinguish (i) genuinely sparse-but-relevant neighborhoods from (ii) dense hub-like neighborhoods dominated by distractors. The Mediator therefore conditions on a blurred trust sensor, where “High” trust can mean either meaningful evidence concentration or simply high connectivity.


#### Graph Trust vs. Semantic Relevance

A deeper issue revealed by the case analysis is a fundamental mismatch between **topological centrality** and **semantic correctness**.

In Case 2 of the paper, the question concerns “VCU” (Virginia Commonwealth University). The system detects High Trust because “VCU” is a prominent node in the knowledge graph. Based on this signal, the policy skips verification to save cost. The result is a hallucination: the system retrieves information about “VCU Basketball” instead of the university’s founding date.

This failure highlights a critical misconception embedded in the Trust signal. PageRank does not measure truthfulness or relevance. It measures **connectivity and popularity**. In fact, highly central nodes are often more dangerous in multi-hop retrieval because they act as hubs that connect to thousands of loosely related facts. High PageRank increases the surface area for semantic distraction.

In this sense, “High Trust” nodes inject *more noise*, not less, into the context window. The learned policy internalized the rule “High Trust implies Safety,” when the semantic reality is often the opposite. The Trust signal is measuring popularity, which in multi-hop question answering is frequently **negatively correlated with precision**.


#### The “No Signal” State as a Hidden Dominant Failure Mode

The system defines a special “No Signal” state $s_{\emptyset}$ that is entered when entity linking fails. In the HotpotQA distractor setting, where questions are intentionally ambiguous and entities are difficult to ground, entity linking failure is not a rare edge case.

If the probability $P(s_{\emptyset})$ is non-trivial and the policy associated with this state is fixed (likely abstention), then a significant fraction of queries bypass the entire GRACE decision logic. In such cases, the system does not reason conservatively—it simply fails safely.

I don't quantify the frequency of $s_{\emptyset}$. If, for example, 30% of queries enter this state, then for 30% of the dataset the “GRACE framework” is not exercised at all. The apparent robustness is then partly an artifact of early failure rather than adaptive decision-making. This creates a blind spot in evaluation: safety is achieved not through reasoning, but through pipeline fragility.

#### Discretization and Aliasing in the Quality Signal $Q$

The Quality signal $Q$ aggregates multiple structural metrics—Path Length $\lambda$, Coherence $y$, and Diversity $H$—via independent binning and summation:

$$
Q = \text{Bin}(\lambda) + \text{Bin}(y) + \text{Bin}(H)
$$

This construction is mathematically problematic. The components have different semantics and non-aligned monotonicities. Shorter paths are usually better, higher coherence is better, but diversity can be either beneficial or harmful depending on context. Their relationship to answer quality is not additive.

By collapsing these heterogeneous signals into a single Low/Mid/High bin, GRACE introduces **state aliasing**. Distinct failure modes—such as short but incoherent paths versus long but coherent paths—map to the same $Q$ value. The Mediator is, therefore, unable to learn distinct policies for structurally different problems, because the state representation erases the interactions between components.

---

Taken together, these signal-level failures explain why the Mediator consistently defaulted to abstention. The policy was not overly cautious by design; it was reacting rationally to unreliable, compressed, and misaligned state information.

The game-theoretic framing suggests that behavior emerges from strategic coordination. In practice, behavior was dominated by sensor noise, heavy-tailed distributions, and lossy discretization. Even a perfectly designed controller cannot recover information that has already been discarded.

---

### Statistical Weaknesses 

All experiments were conducted on my fairly basic personal laptop. As a result, the construction of the HotpotQA knowledge graph and the offline calibration of the policy were **computationally expensive and time-consuming**, even at modest scales. When building graph, I had to cap the sample size at 5000 and rely on aggressive pruning to keep runtime manageable. Now, GRACE explicitly depends on graph construction and graph-derived signals as core inputs to the Mediator’s decisions. The policy was learned on a calibration subset of merely $N_{\text{calib}} = 100$ trajectories. Now the discretized state space has size
$$
|S| = 3 \times 3 = 9,
$$
corresponding to the bins of $(T, Q)$.

The joint action space consists of:

- Retriever: 3 actions (Shallow, Deep, Skip),
- Generator: 4 actions (Single-pass, Consistency, Parametric, Abstain),
- Verifier: 2 actions (Run, Skip),

yielding approximately
$$
|A| \approx 3 \times 4 \times 2 = 24
$$
joint actions (or roughly 15 after excluding invalid combinations).

This results in a tabular policy or Q-function with approximately
$$
|S| \times |A| \approx 9 \times 15 = 135
$$
state–action entries.

With only 100 calibration trajectories, the **sample-to-parameter ratio is less than one**:
$$
\frac{N_{\text{samples}}}{\text{Parameters}} = \frac{100}{135} \approx 0.74.
$$

This places the system in a regime of *extreme sparsity*. Most state–action pairs $(s,a)$ are either never observed or observed once at most. Under such conditions, the estimated utilities $Q_b(s,a)$ are dominated by noise and incidental correlations specific to the sampled trajectories.

Standard results for tabular Q-learning indicate that achieving even an $\epsilon$-optimal policy requires on the order of
$
\tilde{O}\left(\frac{|S||A|}{\epsilon^2 (1-\gamma)^3}\right)
$
samples. For any reasonable discount factor and tolerance, this places the required sample count in the **thousands to tens of thousands**

Consequently, the learned "policy” visualized in the results section cannot be interpreted as a converged equilibrium. It is best understood as a snapshot of random initialization noise and severe overfitting to a tiny calibration set. The policy is not meaningfully adaptive, but statistically underdetermined.

#### Precision vs. Recall

In the paper, I claimed success because Effective Reliability (Precision) is higher than the baseline accuracy. Yet, now I realize this is a comparison of apples and oranges. The Baselines are forced to answer (Recall is maximized). GRACE is allowed to abstain (Precision is maximized, Recall is sacrificed). A trivial baseline that answers only the 1 easiest question and abstains on 99 others would have 100% Effective Reliability. Would we call that a "Superior Reasoner"? The correct comparison would be against a Confidence-Threshold Baseline: "If (Logits < X), Abstain"

Now a simple heuristic (token probability) beat my complex system. This further proves that the internal calibration of the LLM is a stronger signal than my external graph metrics ($T, Q$). The "Graph Reasoning" with all the restrictions we've been discussing added noise, not signal.

Here’s a **high-level intuition** that fixes GRACE *without drowning in machinery*, and that stays aligned with everything you’ve already diagnosed.

---

## Future direction

### Pivot 1: From “equilibrium” to “coordination under uncertainty”

Stop asking:

> “What is the equilibrium action?”

Start asking:

> “Given what we know and don’t know, what action reduces uncertainty or risk?”

This reframes the controller as: a **decision maker**, not a referee.

The job is:

- sometimes answer,
- sometimes retrieve more,
- sometimes verify,
- sometimes abstain.

Not because of incentives.
Because of **epistemic uncertainty**.

### Pivot 2: From popularity signals to evidence structure

PageRank answers:

> “How connected is this entity in Wikipedia?”

But RAG needs:

> “Does this evidence actually support *this* query?”

So “trust” should come from:

- agreement across independent evidence,
- semantic consistency,
- stability under retrieval perturbation,
- coherent multi-hop paths.

Intuition:

- **Multiple weak but consistent clues beat one famous node.**
- **Hubs are dangerous, not safe.**

This is why query-conditioned signals (semantic similarity, path agreement, contradiction checks) matter more than global centrality.

### Pivot 3: From single decision to information-seeking behavior

GRACE treated each query as:

> “Answer or abstain?”

But real reasoning is:

> “What do I do *next* to know more?”

Good systems:

- retrieve when uncertain,
- verify when signals conflict,
- stop when evidence converges.

So the controller should value: **information gain**, not just final correctness.

That’s why:

- bandits,
- hierarchical control,
- or simple uncertainty thresholds

work better than equilibrium logic.

### GRACE should be thought of as:

**A sensor-driven decision loop**

- Observe noisy evidence
- Estimate uncertainty
- Choose the cheapest action that reduces risk
- Stop when confidence is justified










