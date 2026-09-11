#lang roulette/example/probalog

% Biomine -- ProbLog's flagship application, and the problem it was
% built for. Biomine is a biological network whose nodes are genes,
% proteins and phenotypes, and whose edges carry a confidence derived
% from database curation and text mining. The standard query is the
% *connection probability*: how likely is it that a path exists between
% a gene and a disease, given that every edge might not be real?
%
% That question is exactly the disjoint-sum problem. Candidate paths
% through a network like this overlap heavily, so multiplying each
% path's probability and adding them up overcounts badly. The answer
% below is the true probability that *some* path survives. See
% semantics/correlation.rkt for the same point in isolation.

% --- The network -------------------------------------------------------
%
%                  BARD1
%                 /     \
%          BRCA1         TP53 ---- MDM2
%                 \     /    \
%                  (0.5)      CDKN2A
%
% Edges are undirected, as in Biomine; the confidence on each is the
% probability that the interaction is real.

Edge("BRCA1",  "BARD1")  :: 0.9.
Edge("BARD1",  "TP53")   :: 0.7.
Edge("BRCA1",  "TP53")   :: 0.5.
Edge("TP53",   "MDM2")   :: 0.8.
Edge("TP53",   "CDKN2A") :: 0.6.
Edge("MDM2",   "CDKN2A") :: 0.4.

% Phenotype links.
Edge("CDKN2A", "melanoma") :: 0.7.
Edge("BRCA1",  "breast_cancer") :: 0.85.

% --- Undirected connectivity -------------------------------------------
% Each edge is usable in either direction, and the same fact -- so the
% same random variable -- backs both.

Linked(x, y) :- Edge(x, y).
Linked(x, y) :- Edge(y, x).
Linked(x, z) :- Linked(x, y), Edge(y, z).
Linked(x, z) :- Linked(x, y), Edge(z, y).

% --- Connection probabilities -------------------------------------------

% One edge, so just its confidence.
? Linked("BRCA1", "breast_cancer").     % 0.85

% BRCA1 to TP53 has two routes: the direct 0.5 edge, and BARD1 in
% between at 0.9 * 0.7. They share no edges, so this one is
% 1 - (1 - 0.5)(1 - 0.63) = 0.815.
? Linked("BRCA1", "TP53").              % 0.815

% TP53 to CDKN2A: direct at 0.6, or via MDM2 at 0.8 * 0.4.
? Linked("TP53", "CDKN2A").             % 1 - 0.4*0.68 = 0.728

% The headline query, and the one that shows why this needs exact
% inference. There are four BRCA1 -> melanoma paths:
%
%   BRCA1-TP53-CDKN2A-melanoma                   0.21
%   BRCA1-BARD1-TP53-CDKN2A-melanoma             0.2646
%   BRCA1-TP53-MDM2-CDKN2A-melanoma              0.112
%   BRCA1-BARD1-TP53-MDM2-CDKN2A-melanoma        0.14112
%
% Every one of them ends on the CDKN2A-melanoma edge, and they share
% plenty else besides. Combining them as if they were independent
% gives 1 - prod(1 - p) = 0.5569, which is far too high. The exact
% answer is 0.4153 -- and since the graph happens to be a chain of
% three edge-disjoint segments, it factors as 0.815 * 0.728 * 0.7,
% which is a convenient way to check it by hand.
? Linked("BRCA1", "melanoma").          % 0.415324, not 0.5569

% The reverse direction is the same question on an undirected graph.
? Linked("melanoma", "BRCA1").          % 0.415324

? Linked("BARD1", "melanoma").
? Linked("MDM2",  "breast_cancer").

% --- Conditioning on a validated interaction ----------------------------
%
% A wet-lab experiment confirms the TP53 -- CDKN2A interaction. Every
% connection that could route through it goes up.

! Edge("TP53", "CDKN2A").

? Linked("BRCA1", "melanoma").  % 0.5705, up from 0.4153
? Linked("TP53",  "CDKN2A").    % #t
? Linked("BRCA1", "TP53").      % 0.815, untouched: a different edge

% --- Conditioning on a negative result ----------------------------------
%
% A follow-up fails to reproduce the direct BRCA1 -- TP53 interaction.
% BRCA1 now has to reach TP53 through BARD1, so anything downstream of
% TP53 drops.

! ~Edge("BRCA1", "TP53").

? Linked("BRCA1", "TP53").      % 0.9 * 0.7 = 0.63
? Linked("BRCA1", "melanoma").  % 0.63 * 0.7 = 0.441
? Linked("BRCA1", "breast_cancer").  % 0.85, on its own edge throughout
