#lang roulette/example/probalog

% Derivations that share base facts have to be combined exactly. This
% is the "disjoint-sum problem", and the reason an engine that just
% multiplies and adds probabilities as it goes gets wrong answers.
%
% Each section is a program with a hand-computable answer, next to
% what a rule-at-a-time engine would produce instead.

% --- 1. Independent derivations ---------------------------------------
%
%     s --> a --> t          Two routes, disjoint edges. All four are
%      \         /           independent, so inclusion-exclusion
%       -> b -->             happens to be right here.

IEdge("s", "a") :: 0.5.
IEdge("a", "t") :: 0.5.
IEdge("s", "b") :: 0.5.
IEdge("b", "t") :: 0.5.

IPath(x, y) :- IEdge(x, y).
IPath(x, z) :- IPath(x, y), IEdge(y, z).

? IPath("s", "t").          % 1 - (1 - 0.5*0.5)^2 = 0.4375

% --- 2. Derivations sharing a base fact -------------------------------
%
%              --> a -->     Two routes again, but both through the
%     s --> m /         \ t  single edge s->m, and every other hop is
%              --> b -->     certain. So s reaches t exactly when
%                            SEdge("s","m") holds.
%
% Treating the two derivations as independent 0.5 events would give
% 1 - 0.5^2 = 0.75. They are not independent: both depend on the same
% edge, and the answer reflects that.

SEdge("s", "m") :: 0.5.
SEdge("m", "a").
SEdge("a", "t").
SEdge("m", "b").
SEdge("b", "t").

SPath(x, y) :- SEdge(x, y).
SPath(x, z) :- SPath(x, y), SEdge(y, z).

? SPath("s", "t").          % 0.5, not 0.75

% --- 3. Partially shared derivations ----------------------------------
% The general case: two routes sharing the bridge b1->b2, each with
% one private uncertain edge.

PEdge("s",  "b1").
PEdge("b1", "b2") :: 0.8.       % the shared bridge
PEdge("b2", "l")  :: 0.6.
PEdge("b2", "r")  :: 0.6.
PEdge("l",  "t").
PEdge("r",  "t").

PPath(x, y) :- PEdge(x, y).
PPath(x, z) :- PPath(x, y), PEdge(y, z).

? PPath("s", "t").          % 0.8 * (1 - 0.4*0.4) = 0.672

% --- 4. A fact used twice in one rule body ----------------------------
% Requiring the same fact twice is the same as requiring it once.

Risk("host") :: 0.4.
DoubleRisk(x) :- Risk(x), Risk(x).

? DoubleRisk("host").       % 0.4, not 0.16

% --- 5. Two declarations of the same fact -----------------------------
% Each `::` statement is its own independent coin flip, even when two
% of them name the same fact, so the fact holds if either came up
% heads. Worth knowing before writing it by accident: two lines that
% look like a restatement of one probability are two chances at it.

Twice("x") :: 0.5.
Twice("x") :: 0.5.

? Twice("x").               % 1 - 0.5*0.5 = 0.75

% --- 6. A rule that re-derives a base fact ----------------------------
% Same thing, across a fact and a rule rather than two facts.

Direct("y")   :: 0.5.
Indirect("y") :: 0.5.
Direct(x) :- Indirect(x).

? Direct("y").              % 0.75

% --- 7. Conditioning respects the sharing too -------------------------

! PEdge("b1", "b2").

? PPath("s", "t").          % 1 - 0.4*0.4 = 0.84
? PEdge("b2", "l").         % 0.6, independent of the bridge

! ~PPath("s", "t").

% Both private edges must now be absent. A certain answer prints as
% #f rather than as a one-outcome distribution.
? PEdge("b2", "l").         % #f
? PEdge("b2", "r").         % #f
