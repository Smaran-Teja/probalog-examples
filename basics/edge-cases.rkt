#lang roulette/example/probalog

% Everything the language allows, in the smallest program that shows
% each thing, with the expected answer beside it. For everything it
% doesn't allow, see errors.rkt.

% --- Probability annotations ------------------------------------------

Coin("fair") :: 0.5.

% Omitting `::` means probability 1. These two say the same thing:
Certain("a").
Certain("b") :: 1.

% Probability 0 is allowed. Not quite the same as leaving the fact
% out: the predicate is still declared, so the arity check sees it.
Impossible("c") :: 0.

% Any precision works; what isn't allowed is dropping the leading
% zero (`.5`).
Precise("d") :: 0.125.
Round("e")   :: 0.50.

% A certain answer prints as #t or #f -- a one-outcome table carries
% no information.
? Coin("fair").
? Certain("a").         % #t
? Certain("b").         % #t
? Impossible("c").      % #f
? Precise("d").         % 0.125

% --- Arity ------------------------------------------------------------

% Nullary, but the parens are still required.
Ready() :: 0.75.

% Arguments may mix strings and numbers, including negatives.
Reading("sensor7", 3, -12.5, "celsius") :: 0.9.

% Arity must agree per predicate name; Point/2 and Point3/3 are
% unrelated.
Point(1, 2) :: 0.6.
Point(2, 3) :: 0.6.
Point(3, 4) :: 0.6.
Point3(1, 2, 3) :: 0.6.

? Ready().
? Reading("sensor7", 3, -12.5, "celsius").
? Point(1, 2).
? Point3(1, 2, 3).

% Constants are compared with `equal?`, which distinguishes exact from
% inexact, so this is a *different* fact from Point(1, 2). Write
% numeric keys one way throughout.
? Point(1.0, 2.0).      % #f

% --- Rules ------------------------------------------------------------

% A head may contain constants as well as variables.
Overheating() :- Reading("sensor7", 3, -12.5, "celsius").

% A variable appearing only in the body is projected away: the head
% holds if *some* binding satisfies the body.
High("s1") :: 0.4.
High("s2") :: 0.4.
Warm() :- High(s).

% No variables anywhere: just a conditional fact.
BothHigh() :- High("s1"), High("s2").

% A body may repeat a predicate, joining a relation against itself.
Grandlink(x, z) :- Point(x, y), Point(y, z).

? Overheating().        % 0.9
? Warm().               % 1 - 0.6*0.6 = 0.64
? BothHigh().           % 0.16
? Grandlink(1, 3).      % 0.36

% --- Predicates with no facts -----------------------------------------

% A predicate can be used and never defined: its relation is empty, so
% the rule never fires. Legal on purpose -- it's what a rule looks
% like while its data is still missing. Arity is still checked.
Derived(x) :- NeverDeclared(x).

? NeverDeclared("anything").    % #f
? Derived("anything").          % #f

% Declared and never used is fine too.
Unused("f") :: 0.5.

% --- Queries ----------------------------------------------------------

% A query may name a fact no statement mentions, given matching arity.
? Point(99, 99).        % #f

% Queries don't change the database; only observations do.
? Coin("fair").
? Coin("fair").

% --- Statement layout -------------------------------------------------

% A statement ends at its period, wherever that falls.
Chain(x, w) :-
  Point(x, y),
  Point(y, z),
  Point(z, w).

? Chain(1, 4).          % 0.6^3 = 0.216

% Several statements can share a line, though it reads poorly:
Tiny("g") :: 0.5. Tiny("h") :: 0.5.

% `%` comments run to end of line, and are the only thing besides
% whitespace allowed between statements.
? Tiny("g").            % like this

% --- Observations -----------------------------------------------------

% Observations condition every later query, so order matters relative
% to the queries. It doesn't matter relative to the facts and rules:
% those are all collected first, so the database is complete before
% any observation is applied.

! High("s1").

? Warm().               % #t: s1 alone is enough
? High("s2").           % still 0.4, independent of s1
? BothHigh().           % 0.4: hinges on s2 alone now

% Observing something already certain is allowed; it just adds nothing.
! Certain("a").
! ~Impossible("c").

? Certain("a").
? Impossible("c").

% A negative observation about a derived fact propagates back to its
% causes. Ruling out BothHigh() rules out s2, since s1 is known.
! ~BothHigh().

? High("s2").           % #f
? Warm().               % #t: s1 still holds
