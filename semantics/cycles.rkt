#lang roulette/example/probalog

% Recursion in every shape. Not a model of anything -- each section
% isolates one kind.

% ======================================================================
% 1. A cyclic graph
% ======================================================================
%
%     0 -> 1 -> 2 -> 3 -> 0     the cycle
%     0 -> 2, 1 -> 3            chords, so facts are re-derived many ways
%     4 -> 4                    an isolated self-loop
%     3 -> 5                    a tail: reachable, reaches nothing
%
% Going round a cycle re-derives the same facts by ever longer routes,
% none of which change the answer once the shorter ones are known.
%
% Node names are numbers here rather than strings; an argument may be
% a string, an integer, or a decimal.

Link(0, 1) :: 0.9.
Link(1, 2) :: 0.9.
Link(2, 3) :: 0.9.
Link(3, 0) :: 0.9.
Link(0, 2) :: 0.5.
Link(1, 3) :: 0.5.
Link(4, 4) :: 0.7.
Link(3, 5) :: 0.8.

Reach(x, y) :- Link(x, y).
Reach(x, z) :- Reach(x, y), Link(y, z).

% Inside the cycle every node reaches every other, including itself.
? Reach(0, 3).
? Reach(3, 1).
? Reach(0, 0).

? Reach(0, 5).
? Reach(5, 0).      % #f: node 5 has no outgoing links

% Node 4's self-loop reaches itself, and re-reaching itself any number
% of times adds nothing to the probability.
? Reach(4, 4).      % 0.7
? Reach(4, 0).      % #f

% --- Repeated variable in one clause ----------------------------------
% Both arguments are the same variable, so it matches only self-loops:
% matching binds x on the first, then requires the second to equal it.

SelfLooping(x) :- Link(x, x).

? SelfLooping(4).
? SelfLooping(0).   % #f

% --- Constants in clause position -------------------------------------
% A literal in a body clause restricts the match: `Link(0, y)` ranges
% only over the links out of node 0.

FromZero(y) :- Link(0, y).
IntoZero(x) :- Link(x, 0).
% Two constants and no variables at all: a nullary head that holds
% when both named links do.
ZeroToTwo() :- Link(0, 1), Link(1, 2).

? FromZero(1).
? FromZero(3).      % #f: no direct link 0 -> 3
? IntoZero(3).
? ZeroToTwo().      % 0.9 * 0.9 = 0.81

% ======================================================================
% 2. Mutual recursion
% ======================================================================
%
% Two predicates each defined in terms of the other. Every rule is
% applied every round, so this needs no stratification -- but neither
% predicate is complete until both are.
%
% Parity along a chain 0 - 1 - ... - 6 with two uncertain steps. An
% uncertain step leaves *both* parities possible further along: if
% 2->3 is missing, nothing past node 2 is classified at all.

Step(0, 1).
Step(1, 2).
Step(2, 3) :: 0.6.
Step(3, 4).
Step(4, 5) :: 0.5.
Step(5, 6).

Even(0).
Odd(y)  :- Even(x), Step(x, y).
Even(y) :- Odd(x),  Step(x, y).

? Even(0).          % #t, the base case
? Odd(1).           % #t: certain steps only
? Even(2).          % #t
? Odd(3).           % 0.6, gated by step 2 -> 3
? Even(4).          % 0.6
? Odd(5).           % 0.6 * 0.5 = 0.3
? Even(6).          % 0.3

% Parities needing a different chain length aren't derivable at all.
? Even(1).          % #f
? Odd(2).           % #f

% ======================================================================
% 3. Non-linear recursion
% ======================================================================
%
% Both body clauses of the second rule are recursive, rather than one
% recursive clause and one base relation. It computes the same
% transitive closure by combining two derived pairs instead of
% extending one by an edge.

Hop(0, 1) :: 0.9.
Hop(1, 2) :: 0.9.
Hop(2, 3) :: 0.9.
Hop(3, 0) :: 0.9.

Trans(x, y) :- Hop(x, y).
Trans(x, z) :- Trans(x, y), Trans(y, z).

? Trans(0, 0).      % all the way round: 0.9^4 = 0.6561
? Trans(0, 3).      % three edges: 0.729
? Trans(3, 2).      % 0.729, the other way round

% Same relation and same probabilities as the linear formulation would
% give on this graph. (Not comparable to Reach above, which runs on a
% graph with extra chords.)
? Trans(1, 0).      % 0.729
