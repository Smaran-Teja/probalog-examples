#lang roulette/example/probalog

% Andersen's points-to analysis -- the example Souffle's own tutorial
% is built around, and the core of Doop-style program analysis.
%
% The Datalog is unchanged from the Souffle version. What probabilities
% add is a way to carry *unresolved* analysis facts: a reflective
% allocation whose class name a string analysis could only narrow to
% two candidates, and a virtual call whose receiver type is unknown.
% Instead of dropping one (unsound) or taking both at full strength
% (imprecise), each possibility keeps its confidence, and every derived
% alias comes out with the probability that it actually holds.
%
% One thing to be clear about before reading the numbers: the two
% candidates at each site below are *independent* facts, not an
% exclusive choice. ProbLog would write an annotated disjunction,
%
%     0.6::assign(y,a) ; 0.4::assign(y,b).
%
% meaning exactly one of them holds. Probalog has no such form, and no
% negation to build one out of, so each candidate is its own coin flip
% and both can come up true at once. For a may-analysis that is a
% defensible reading -- the confidences come from separate evidence,
% and points-to sets are unions anyway -- but it does change what
% conditioning on one candidate tells you about the other, as the last
% section shows.

% --- The program under analysis ----------------------------------------
%
%   1  a = new A();                      // o1
%   2  b = new B();                      // o2
%   3  c = a;
%   4  a.f = b;
%   5  d = c.f;
%   6  x = Class.forName(s).newInstance();   // s unresolved
%   7  y = p.get();                          // virtual, receiver unknown

AddressOf("a", "o1").
AddressOf("b", "o2").
Assign("c", "a").
Store("a", "f", "b").
Load("d", "c", "f").

% Line 6: a string analysis narrowed s to "A" or "B" with these
% confidences.
AddressOf("x", "o1") :: 0.7.
AddressOf("x", "o3") :: 0.3.

% Line 7: class-hierarchy analysis says p.get() is A.get (returning a)
% or B.get (returning b), and could not settle the receiver.
Assign("y", "a") :: 0.6.
Assign("y", "b") :: 0.4.

% --- Andersen's rules --------------------------------------------------
% Verbatim from the Souffle tutorial, field-sensitive.

VarPointsTo(v, o) :- AddressOf(v, o).
VarPointsTo(v, o) :- Assign(v, u), VarPointsTo(u, o).
VarPointsTo(v, o) :- Load(v, u, f), VarPointsTo(u, b), FieldPointsTo(b, f, o).

FieldPointsTo(b, f, o) :- Store(u, f, v), VarPointsTo(u, b), VarPointsTo(v, o).

% Two variables may alias if they can point to a common object. Note
% Alias(v, v) holds trivially for any v that points to anything -- the
% usual side condition is v != u, and probalog has no disequality.
Alias(v, u) :- VarPointsTo(v, o), VarPointsTo(u, o).

% --- The certain part of the analysis -----------------------------------

? VarPointsTo("a", "o1").           % #t
? VarPointsTo("c", "o1").           % #t, through the assignment
? FieldPointsTo("o1", "f", "o2").   % #t
? VarPointsTo("d", "o2").           % #t, through the store/load pair

% --- The unresolved part ------------------------------------------------

? VarPointsTo("x", "o1").       % 0.7
? VarPointsTo("x", "o3").       % 0.3
? VarPointsTo("y", "o1").       % 0.6, if p.get() was A.get
? VarPointsTo("y", "o2").       % 0.4, if it was B.get

% x aliases a exactly when the reflective allocation produced an A.
? Alias("x", "a").              % 0.7

% d certainly points to o2, so y aliases d exactly when B.get ran.
? Alias("y", "d").              % 0.4
? Alias("y", "c").              % 0.6

% Both must land on o1, and the two sites are independent choices.
? Alias("x", "y").              % 0.7 * 0.6 = 0.42

% --- Feeding a runtime observation back in ------------------------------
%
% A profiler saw y and d alias on a real execution. y reaches o2 only
% through B.get, so that call is settled.

! Alias("y", "d").

? Assign("y", "b").             % #t: B.get did run
? VarPointsTo("y", "o2").       % #t

% But A.get is *not* thereby ruled out. With an annotated disjunction
% it would be; here the two are independent facts, and knowing one
% fired says nothing about the other. So this is still 0.6, and y's
% points-to set may well contain both objects.
? Assign("y", "a").             % 0.6, unchanged
? Alias("y", "c").              % 0.6, unchanged

% Ruling A.get out takes its own observation. `~` is how an analysis
% result that came back negative gets fed in.
! ~Alias("y", "c").

? Assign("y", "a").             % #f
? VarPointsTo("y", "o1").       % #f
? Alias("x", "y").              % #f: y can no longer reach o1

% The reflective site at line 6 was never involved in any of this, so
% it sits at its prior throughout.
? VarPointsTo("x", "o1").       % still 0.7
