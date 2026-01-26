# Adaptive Context GraphRAG

**Tags:** Project, RAG, Graph, Leiden, Louvain, Node2Vec

## Abstract

Adaptive Context GraphRAG proposes augmenting Leiden-based GraphRAG communities with a small set of “context nodes” selected by embedding similarity and graph proximity, aiming to recover semantic links that hard partitioning may cut. Here, I show that this post-processing lacks statistical validation and relies on structural embeddings (Node2Vec) in ways that can inflate context, create circular evaluation, and weaken the original design guarantees of GraphRAG communities.

## Some thoughts...

To be honest, I first learned about the concept of RAG only after starting this project. The idea was proposed by one of my teammates, who had previous experience working with RAG. At the beginning, I mostly followed this direction without fully understanding all the assumptions behind it. During the project, and especially after we started analyzing our own results, we gradually noticed several flaws in our approach, which I will discuss in the following sections. The orginial paper can be found [here](https://drive.google.com/file/d/1LNqDFwCyy6PVhInOM09R4LemorYd7k2e/view?usp=sharing).

Even with these issues, I am still thankful that we chose this topic. Many of the problems we encountered were not because the idea itself was weak, but because of limitations in how we initially thought about the problem. Through making these mistakes, I ended up learning much more about RAG than I expected. Over time, this also helped me develop a genuine interest in the area, especially in understanding where current GraphRAG methods succeed and where they fail.

---

## Overview

The initial motivation was the observation that GraphRAG relies too heavily on the “hard partitioning” produced by Leiden community detection. Leiden is designed to optimize graph connectivity rather than semantic meaning. Because of this, nodes that are semantically related but only loosely connected in the graph can be placed into different communities. Once these communities are summarized independently, semantic information across communities is largely lost. This limitation motivated our main intervention.

Instead of modifying Leiden directly, our approach post-processes its output. We first run standard Leiden to obtain communities $C_1, \ldots, C_k$. Next, we embed nodes using Node2Vec and/or SBERT, and identify “misaligned nodes,” defined as nodes whose embedding similarity is higher to a different community than to their original one. We then attach a small number of these nodes as context nodes to the target community. The original community structure is kept unchanged, but each community is augmented with additional semantic connections.

Formally, we define the following heuristic score:

$$
s(v, C_j) = \frac{(\text{sim}(v, C_j))^2}{1 + d(v, C_j)}
$$

where the score combines semantic similarity (cosine similarity), a hop-distance penalty, and a centrality penalty to reduce the influence of highly connected hub nodes.

This procedure results in **overlapping, semantically enriched communities**, which are then used for community-level summary generation and retrieval-time Cypher queries.

---

## GraphRAG

To understand the flaws in Adaptive Context GraphRAG, we first need to understand the basic components of GraphRAG.

[GraphRAG](https://arxiv.org/pdf/2404.16130) builds a knowledge graph from text (entities, relations, claims), then uses **community detection** to partition that graph into groups that can be summarized and retrieved efficiently.

At a high level, the pipeline logic is:

1. **LLM extraction:** convert text semantics into graph structure (nodes, edges, edge weights from repeated relations).
2. **Community detection (Leiden):** partition the graph into **strongly connected** groups.
3. **LLM summarization:** summarize each group (often hierarchically bottom-up).
4. **Query-time use:** retrieve and combine community summaries to answer questions.

So the community algorithm is mainly an **indexing and summarization organizer**: it provides coherent “units” for reporting and for retrieval-time aggregation.

---

## Leiden

[Leiden](https://arxiv.org/pdf/2404.16130) is a **community detection** algorithm. Its goal is to group nodes into communities such that:

1. nodes inside a community are strongly related
2. nodes in different communities are weakly related

The difficulty is that:

- the graph is large,
- the number of possible partitions is enormous,
- finding the best partition exactly is computationally infeasible.

So Leiden does not “reason about semantics”, it optimizes a structural quality function, typically Modularity or Constant Potts Model (CPM)

---

### Modularity

Measures how good a partition is by comparing:

1. **Actual number of edges inside a community**
2. **Expected number of edges inside that community** if edges were placed “randomly” but node degrees stayed the same (the **configuration model**)

$$
H=\frac{1}{2m}\sum_{c}\left(e_c-\gamma\frac{K_c^2}{2m}\right)
$$

where:

- $e_c$: internal edges (or weight) inside community $c$
- $K_c$: sum of node degrees in $c$
- $m$: total edges in the graph
- $\frac{K_c^2}{2m}$: _expected_ internal edges under the configuration model
- $\gamma$: resolution parameter

Here:

- Modularity gives **high score** when communities have **more internal edges than would expect by chance** (given the same degrees).
- It gives **low score** when a community has about the same internal density would get from a random wiring with the same degrees.

---

### CPM

Referred in the paper as **a better quality function**

$$
H=\sum_{c}\left(e_c-\gamma\binom{n_c}{2}\right)
\quad\text{where}\quad
\binom{n_c}{2}=\frac{n_c(n_c-1)}{2}
$$

- $n_c$: number of nodes in community $c$
- $\binom{n_c}{2}$: number of possible internal pairs inside $c$

Both modularity and CPM share the same overall shape:

1. **Reward internal edges** via (+e_c)
2. **Penalize large communities** using a term that grows roughly like “size squared”
3. Include a **resolution parameter $\gamma$**, where larger $\gamma$ tends to produce **more, smaller communities**

**Key difference:**

- **Modularity penalty** uses $\frac{K_c^2}{2m}$, which depends on global graph statistics ($m$) and degree sums ($K_c$).
- **CPM penalty** uses $\binom{n_c}{2}$, which depends only on community size, via the number of possible internal pairs.

The paper argues CPM **overcomes some limitations of modularity**, while behaving similarly as a resolution-controlled community quality function.

#### CPM as a density threshold

Let $\rho_c$ be the internal edge density of community $c$:

$$
\rho_c := \frac{e_c}{\binom{n_c}{2}}
$$

For unweighted graphs, $\rho_c \in [0,1]$ and measures “what fraction of possible pairs actually have an edge”

Substitute $e_c=\rho_c\binom{n_c}{2}$ into the CPM term:

$$
e_c-\gamma\binom{n_c}{2}
= \binom{n_c}{2}(\rho_c-\gamma)
$$

So each community contributes:

- positive value if $\rho_c > \gamma$
- negative value if $\rho_c < \gamma$

That is why $\gamma$ acts like a **density threshold**.

---

#### Each internal edge gives +1 reward

The first term is $e_c$. If add one internal edge inside community $c$, then $e_c$ increases by 1, and the objective $H$ increases by $+1$ (holding everything else fixed). For weighted graphs, it is “+weight of that edge,” same idea.

#### Each possible internal pair costs $\gamma$

The penalty term is $\gamma\binom{n_c}{2}$. The $\binom{n_c}{2}$ counts how many node pairs are allowed to be “inside the same community.” CPM charges $\gamma$ for each possible pair, even if those pairs do not have edges.

This is why large, sparse communities get punished: they contain many possible pairs, but not enough actual edges to “pay for” them.

#### A community is worth it only if its density is high enough

From $\binom{n_c}{2}(\rho_c-\gamma)$, the score improves when $\rho_c \ge \gamma$. This matches the paper’s statement that “communities should have a density of at least $\gamma$.”

#### Density between communities should be lower than $\gamma$

Consider two communities $C$ and $D$. If we define a between-community density:

$$
\text{between-density}(C,D)=\frac{E(C,D)}{|C||D|}
$$

where $E(C,D)$ is the number of edges connecting nodes in $C$ to nodes in $D$, then:

- if between-density is large (relative to $\gamma$), merging tends to be beneficial
- if between-density is small (below $\gamma$), merging is not worth it

This matches the paper’s intuition that “density between communities should be lower than $\gamma$.”

#### Higher $\gamma$ leads to more communities

Increasing $\gamma$ raises the density requirement for a set of nodes to remain together. That makes:

- sparse regions more likely to split
- merges harder to justify

So higher $\gamma$ typically yields smaller, denser communities.

---

### Leiden repeats three phases

1. Move individual nodes to improve the quality function
2. Refine communities internally
3. Aggregate the graph and repeat

This continues until nothing improves.

##### Move phase (local improvement)

For each node:

- consider moving it to a neighboring community
- compute whether the quality increases
- if yes, move it

This produces a locally improved partition: after the phase ends, no single node move improves the objective.

However, node-level optimality is not enough. You can still end up with communities that are poorly connected internally (a known Louvain failure mode).

#### Refinement phase (Leiden’s key idea)

After node moves, a community may be:

- internally disconnected,
- connected only by weak links,
- or made of loosely related subgroups,

even if no single node wants to move.

Refinement works inside each community:

1. temporarily “reset” its internal structure (treat nodes as singletons)
2. merge nodes only if the merge improves the objective
3. restrict merges so they stay within the original community

Conceptually, refinement asks:
“Is this community really one dense group, or is it secretly several groups glued together?”

CPM-based justification:

- If a community can be split into two parts whose connection is weaker than the $\gamma$-threshold, splitting increases the objective.
- Refinement follows the logic of the objective, rather than guessing based on semantics.

Non-greedy aspect:

- Leiden does not always pick the single best merge at each step.
- It accepts improving merges (sometimes with randomness), which helps avoid getting stuck in suboptimal structures. The paper proves this preserves reachability of optimal partitions under certain conditions.

#### Aggregation phase (compression)

After refinement:

- each refined community becomes a single node
- edges between communities become weighted edges in the compressed graph

Then Leiden repeats move → refine → aggregate on this smaller graph.

Why refinement must happen before aggregation:

- If aggregate too early, internal structure will be destroyed and may lock in bad communities that cannot be repaired.
- Leiden’s ordering is designed to only compress communities after they have been structurally “validated” by refinement.

Why Leiden can be fast in practice:

- it revisits only nodes whose neighborhood changed
- it avoids rescanning the entire graph unnecessarily

---

### Leiden guarantees

After each iteration, Leiden ensures:

1. communities are $\gamma$-separated (no merge can improve the objective)
2. communities are $\gamma$-connected (a stronger condition than plain connectedness)

After a stable iteration (partition does not change), Leiden also implies:

1. node optimality: no single node move can improve the objective
2. stronger internal quality properties (for CPM, this is described via recursive $\gamma$-density style conditions)

With continued iterations, Leiden converges toward partitions where communities are uniformly $\gamma$-dense and subset optimal (no subset of nodes can move to another community to improve the objective).

**Core objective:**

- reward for edges kept inside communities
- penalty for grouping too many nodes together

So a community must be dense enough to be “worth it.”

## How Leiden is used in GraphRAG

In GraphRAG, Leiden is the community detection step that turns the extracted knowledge graph into clusters so the system can summarize the corpus in a scalable divide-and-conquer way.

### Where Leiden sits in the pipeline

After LLM extracts entities and relationships from text and builds a knowledge graph, GraphRAG runs community detection (for example, Leiden) to produce communities. These communities are summarized by an LLM and later used to answer questions.

### How GraphRAG gets a hierarchy

A single run of Leiden produces one partition. GraphRAG gets a hierarchy by applying Leiden recursively:

- run Leiden on the full graph to get top-level communities
- run Leiden again inside each community to get sub-communities
- repeat until communities can no longer be meaningfully partitioned

At each level, communities are:

- mutually exclusive: each node belongs to exactly one community at that level
- collectively exhaustive: all nodes are covered

This makes the communities suitable units for divide-and-conquer summarization.

### How GraphRAG uses communities

Indexing-time: generate community summaries bottom-up

- for leaf communities: pack node/edge/claim descriptions into the context window (prioritizing prominent elements) and summarize
- for higher-level communities: if raw element summaries are too large, substitute lower-level community summaries to fit the context window, then summarize to produce a higher-level report

Query-time: answer using community summaries (map-reduce style)
Given a question:

1. chunk the community summaries
2. map: generate intermediate answers per chunk, with a helpfulness score
3. reduce: combine the best intermediate answers into a final global answer

**GraphRAG evaluates different hierarchy levels:**

- $C0$: root-level community summaries (few, broad)
- $C1$–$C3$: increasingly fine-grained sub-communities

## Why GraphRAG chose Leiden

GraphRAG needs community detection mainly to:

1. partition the graph into groups for parallel summarization
2. build a hierarchical partition via repeated partitioning
3. ensure each level is mutually exclusive and collectively exhaustive
4. avoid known connectivity issues that can produce incoherent communities

Leiden fits because:

- it finds strongly connected groups efficiently
- it provides strong connectivity and separation guarantees compared to Louvain
- it scales well

Where semantics enters GraphRAG:

- LLM extraction step converts text semantics into graph nodes/edges/weights
- Leiden then clusters purely by graph structure

---

## Adaptive Context contradicts original design

Under $\gamma$CPM, a partition is “good” precisely because it increases the chosen objective. In CPM terms, communities are preferred when they pass a $\gamma$-controlled density threshold; weak cross links are exactly what the objective tries to separate. Thus, when Leiden **excludes** a node from a community, it is not merely being “harsh”; it is expressing that—under the graph structure and the objective—the node does not belong in that dense set.

Adaptive Context then reaches outside the cluster (which Leiden explicitly separated) and reintroduces external nodes as “context nodes” based on embedding similarity and hop-distance. This creates a **two-objective pipeline**:

1. spend computation to find an optimized partition under a connectivity objective
2. then partially undo the separation using an embedding-based semantic heuristic

**This is the theoretical contradiction:**

- the system first treats “optimal cuts” as meaningful outputs of a principled objective
- then it treats those same cuts as errors to be patched by a secondary rule

The project argues the patch is required to capture semantic links missed by harsh partitioning. But GraphRAG’s core premise is that text semantics are already **projected into graph structure** via extracted entities/relations and their repeated co-occurrence (edge weighting).

Under that premise, if “semantic links” were structurally significant in the constructed graph, Leiden would tend to preserve them as strong internal connectivity. The fact that such links are cut suggests they are **weak structural ties** (at least in the graph as built). Reintroducing them through a separate heuristic risks adding connections that the structural objective treated as insufficiently supported.

GraphRAG’s workflow relies on communities being coherent summarization units. Adaptive Context creates **overlapping enrichment** after the partitioning step, meaning the summarization stage is now operating on objects that are no longer aligned with the structural guarantees and separations that motivated the partition in the first place.

---

## Absence of Statistical Validation

Even if we accept the premise that adaptive context is required, the project does not provide any statistical validation of the claims. The decision to add a context node is based on a heuristic score combining:

- Cosine similarity
- Graph distance

Intuitively, this means:

> “If a node looks similar and is close in the graph, we add it to the context”

At first glance, this sounds reasonable.
But the problem is **how do we know this similarity is not just accidental?**

In statistics and machine learning, when we claim that _A is related to B_, we usually ask:

> “Would we see this level of similarity **even if there was no real relationship**?”

To answer that, we normally need **at least one** of the following:

- A **null model** (what similarity looks like when connections are random)
- A **probability test** (how likely is this similarity under randomness?)
- A **significance threshold** (for example: only accept relations that happen less than 5% of the time by chance)

This project uses **none of these**.

Without this comparison, the score has **no reference point**.
A value like `0.73` for cosine similarity means nothing by itself unless we know:

- Is `0.73` rare?
- Or is it very common in this graph?

**This is especially dangerous in dense graphs built from text, where:**

- Many nodes are weakly similar to many others
- High-dimensional embeddings almost always show _some_ similarity
- Short graph paths are common

So even **unrelated nodes** can appear:

- moderately similar
- relatively close

If we always accept these signals without statistical testing, the system will:

- keep adding nodes
- keep expanding context
- include many nodes that _look_ related but are not truly meaningful

This causes **false positives**.

> The system says this node belongs in the context, but it actually does not

Over time, this leads to **context inflation**:

- the context becomes larger
- noisier
- less precise

Instead of correcting meaning, the system **dilutes it**.

> The system adds context **because it can**, not because it **should**

---

## Error when treating Node2Vec as Semantic

[Node2Vec](https://arxiv.org/pdf/1607.00653) is a method for learning **node embeddings from graph structure**, not from text or meaning.

Node2Vec never looks at:

- words
- sentences
- definitions
- labels
- semantics in the linguistic sense

It performs **random walks** on the graph to learn embeddings.

A random walk works like this:

1. Start at a node
2. Randomly choose one of its neighbors
3. Move to that neighbor
4. Repeat many times

This produces sequences of node IDs, for example:

```
A → B → D → C → B → E
```

The walk has **no understanding of meaning**. It only follows edges.

Random walks are useful because they capture **local graph structure**:

- Nodes that appear close together in a walk are:
  - close in the graph, or
  - connected through many paths

- Nodes that appear in similar walks tend to:
  - have similar neighbors
  - play similar structural roles

Node2Vec runs many walks from every node, so it observes the graph from many perspectives.

Key idea is that Node2Vec **treats random walks like sentences**. The mapping is:

| Natural language | Graph setting            |
| ---------------- | ------------------------ |
| word             | node ID                  |
| sentence         | random walk              |
| context          | nearby nodes in the walk |

So the walk

```
A → B → D → C → B → E
```

is treated like the sentence:

```
"A B D C B E"
```

But these “words” are **node IDs**, not real words.

Next, Node2Vec trains a **Skip-gram model** (the same objective used in word2vec).

Skip-gram has a simple goal:

> Given a center item, predict which items appear near it.

In text:

- if “cat” often appears near “animal”,
- their embeddings become close.

In Node2Vec:

- given a center **node**,
- predict which **other nodes** appear near it in random walks.

**Example:**

From the walk:

```
A → B → D → C → B → E
```

If the context window size is 2, then for node `D`, the context nodes are:

```
B, C
```

The model learns training pairs like:

```
(D → B)
(D → C)
```

It adjusts the vector of `D` so that it is good at predicting `B` and `C`.

After many walks and many updates:

- Each node gets a vector in ℝⁿ
- Nodes with **similar walk contexts** get similar vectors
- Similarity is usually measured using cosine similarity

Crucially, the model only uses:

- co-occurrence frequency in walks
- graph connectivity patterns

This leads to Skip-gram **does not know why** nodes co-occur. It does not know:

- meaning
- text
- labels
- semantics

It only knows:

- which nodes tend to appear near each other in graph paths

So if two nodes:

- appear in similar random walks
- have overlapping neighborhoods
- play similar structural roles

their embeddings will be close — **even if they represent completely different concepts**.

Therefore, when Node2Vec outputs similar embeddings, it is saying:

> “These nodes occupy similar positions in the graph.”

It is **not** saying:

> “These nodes have similar meaning in language.”

In Node2Vec, the “context” of a node is defined **only by graph paths**, not by semantics.

As per the original Node2Vec paper claims, Node2Vec captures:

- **structural similarity** (e.g., hubs, bridges)
- **role similarity** (nodes that function similarly)
- **neighborhood overlap**

These are **topological properties**, not semantic ones.

---

## Circular Evaluation

The evaluation uses Node2Vec embeddings to measure:

- `Precision@k`
- `Cross-cluster similarity`

But Node2Vec was already used to construct the communities.

This creates circular reasoning:

1. The algorithm adds nodes that are close in Node2Vec space.
2. The evaluation checks whether nodes are close in Node2Vec space.
3. The result is guaranteed to look good.

This does not demonstrate real improvement.

A valid evaluation would require:

- Independent semantic embeddings (e.g., SBERT)
- Or downstream QA accuracy
- Or human judgment of answer quality

None of these are provided.

---

## Cost

GraphRAG is already expensive because it:

- Extracts entities
- Builds a graph
- Detects communities
- Summarizes each community with an LLM

Adding context nodes increases summary size.

Larger summaries mean:

- More tokens
- Higher cost
- Slower indexing

The paper itself admits limited LLM budget, which strongly suggests the approach does not scale.

When nodes appear in multiple communities:

- They are summarized multiple times.
- They are retrieved multiple times.
- LLM reads the same information repeatedly.

This wastes both indexing and inference tokens.

## Is graph a good approach?

What I notice is that we usually don’t need GraphRAG, because the engineering + indexing cost is high and strong baselines already solve many issues. I don't mean graph is useless, but it should **not be the first thing** we should reach for. The paper did admit that, in some cases, graph-free global summarization competes well with GraphRAG. Microsoft team, though, did walk around this issue of expensive indexing by offloading work from index time to query time in their [LazyGraphRAG](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost). I guess GraphRAG can be really good for XAI, but I don't think it's the best approach in general. There are other ways to do it, which I have discussed [here](?project=rag101.md).
