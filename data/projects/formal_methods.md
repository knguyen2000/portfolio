# Formal Methods

**Tags:** Project, RAG, Graph, Leiden, Louvain, Node2Vec

## Abstract

## Overview

## Model

A model \approx reality

Formal Methods is a field that uses mathematical modeling and logic to verify that a system (software or hardware) behaves exactly as intended (a.k.a use math to prove correctness)

When you write software or design hardware, this "real system" is messy and infinitely complex. It includes:

- Source Code: Thousands of lines of Java, C++, or Verilog.
- Hardware: Physical CPU, memory registers, and electrical signals.
- Environment: External inputs like a user clicking a button or a sensor reading temperature.

### Syntax vs Semantics

Syntax: The "grammar" of the system. It defines what is legal or legal.

Semantics: The "meaning" of the system. It defines what legal inputs actually do.

Example:

- Syntax: `x = 1` (legal in C++)
- Semantics: `x` now holds the value 1 (what it means)

> Syntax = representation; Semantics = content

### Semantic Abstraction: From Real to Model

Real system is too large to check every possible state, thus, imppossible to perform mathematical proofs directly on. Instead, we use **Semantic Abstraction** to create a **Semantic Model**. By refining it into a semantic model, we turn a programming problem into a graph theory problem.

- Selection: You decide which parts of the real system actually matter for the property you want to prove.
- Simplification: You ignore details like variable names or UI colors and focus on the logic.
- Nodes and Transitions: You represent the system's behavior as a **Transition System** ($\mathcal{T}$), where **States** are the nodes and **Stepwise Behavior** are the transitions.

### Transition Systems

A Transition System ($\mathcal{T}$) is a **State Graph** that models a real system.

- Nodes (States): The different situations the system can be in.
- Edges (Transitions): The moves between situations. Written as a triple (current state, action, next state)
- Atomic Propositions ($AP$): Basic facts that are true in a state (e.g., "the light is green" or "message delivered").
- Labeling Function ($L$): Maps each state to the set of APs that are true in that state. Example: If $p \in L(s)$, then the property $p$ is true in state $s$.
- Nondeterminism: In complex systems, one action might lead to several possible outcomes. We model this as a transition to a set of states.
- Independent Actions: Parallel execution of actions $\alpha$ and $\beta$ that do not affect each other, often modeled using **interleaving**.
- Dependent Actions: Actions that compete for resources (e.g., $x := x + 1$ and $y := 2 * x$), often resulting in **competition**.

**State Graph $\neq$ Flowchart**

A Flowchart represents the **Control Flow** (static code structure), whereas a Transition System represents the **State Space** (dynamic runtime behavior).

| Feature     | Flowchart (Control Flow Graph)       | Transition System (State Graph)            |
| :---------- | :----------------------------------- | :----------------------------------------- |
| Nodes       | Instructions / Code Blocks           | Concrete Values (e.g., x=1, y=2)           |
| Edges       | Control transfer (Jump/Branch)       | State mutation (Action)                    |
| Size        | Linear with Lines of Code ($O(LOC)$) | Exponential with Memory Bits ($O(2^N)$)    |
| Determinism | Usually deterministic                | Often nondeterministic (concurrency/input) |



