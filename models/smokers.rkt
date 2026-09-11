#lang roulette/example/probalog

% "Friends and smokers", the canonical probabilistic logic program.
% People smoke from stress or from a friend's influence, and smokers
% may develop asthma.
%
% Friendship is symmetric, so Smokes/1 recurses around cycles. Alice
% and Bob share friends, so their chances of smoking are correlated
% rather than independent, and the answers reflect that exactly.
%
% ProbLog writes probabilistic rules (`0.3::stress(X) :- person(X).`).
% Probalog puts probabilities on facts only, so the same thing is a
% certain rule together with a ground probabilistic fact. Stress/1,
% Influences/2 and AsthmaProne/1 are all of that kind -- not data,
% but the rules' coin flips made explicit.

% --- The social network ------------------------------------------------
%
%     alice --- bob
%        \      /
%         carol --- dave --- erin
%
% Stated in both directions rather than closed by a rule, which would
% add nothing but redundant derivations.

Friend("alice", "bob").
Friend("bob",   "alice").
Friend("alice", "carol").
Friend("carol", "alice").
Friend("bob",   "carol").
Friend("carol", "bob").
Friend("carol", "dave").
Friend("dave",  "carol").
Friend("dave",  "erin").
Friend("erin",  "dave").

% --- The rules' coin flips ---------------------------------------------

% Stressed enough to take up smoking alone. Dave has a hard job.
Stress("alice") :: 0.2.
Stress("bob")   :: 0.2.
Stress("carol") :: 0.2.
Stress("dave")  :: 0.5.
Stress("erin")  :: 0.2.

% Whether x's smoking rubs off on y. Directional, unlike friendship.
Influences("alice", "bob")   :: 0.3.
Influences("bob",   "alice") :: 0.3.
Influences("alice", "carol") :: 0.3.
Influences("carol", "alice") :: 0.3.
Influences("bob",   "carol") :: 0.3.
Influences("carol", "bob")   :: 0.3.
Influences("carol", "dave")  :: 0.3.
Influences("dave",  "carol") :: 0.3.
Influences("dave",  "erin")  :: 0.6.   % erin looks up to dave
Influences("erin",  "dave")  :: 0.1.

AsthmaProne("alice") :: 0.4.
AsthmaProne("bob")   :: 0.4.
AsthmaProne("carol") :: 0.4.
AsthmaProne("dave")  :: 0.4.
AsthmaProne("erin")  :: 0.4.

% --- The model ---------------------------------------------------------

Smokes(x) :- Stress(x).
% The recursive clause -- the one that goes around cycles.
Smokes(x) :- Friend(x, y), Smokes(y), Influences(y, x).

Asthma(x) :- Smokes(x), AsthmaProne(x).

% y appears only in the body, so it is projected away: "does there
% exist such a friend", over the whole database at once.
HasSmokingFriend(x) :- Friend(x, y), Smokes(y).

% --- Priors ------------------------------------------------------------
% Everyone is above their own Stress prior thanks to influence paths.

? Smokes("alice").
? Smokes("bob").
? Smokes("carol").
? Smokes("dave").
? Smokes("erin").

? Asthma("alice").
? Asthma("erin").

? HasSmokingFriend("erin").

% --- Observing a diagnosis ---------------------------------------------

! Asthma("dave").

% Evidence dave smokes, propagating outward along the graph. Erin,
% strongly influenced by him, rises most; alice and bob via carol.
? Smokes("dave").       % #t
? Smokes("erin").
? Smokes("carol").
? Smokes("alice").
? Smokes("bob").

% --- Observing an absence ----------------------------------------------

! ~Smokes("carol").

% Carol was the only path between dave and alice/bob, and one of the
% two friends who could have influenced them, so they now drop below
% even their priors. Dave loses the carol route too, leaving his own
% stress to explain the asthma.
? Smokes("alice").
? Smokes("bob").
? Smokes("dave").
? Stress("dave").       % 0.98
? Smokes("erin").
