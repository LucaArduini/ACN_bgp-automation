%% PLI (MILP): min | 2*c'*x - sum(c) |   con x binarie

clear; clc;

%% ====== DATI ======
c = [45; 0; 31; 0; 15; 30];
c = c(:);
n = numel(c);
Csum = sum(c);

%% ====== VARIABILI ======
% z = [x; t]
N = n + 1;
idx_t = N;

f = zeros(N,1);   % min t
f(idx_t) = 1;

intcon = 1:n;     % x binarie/intere, t continua

lb = [zeros(n,1); 0];
ub = [ones(n,1);  inf];

%% ====== VINCOLI: t >= S e t >= -S ======
% S = 2*c'*x - sum(c)
% (1)  2*c'*x - t <= sum(c)
% (2) -2*c'*x - t <= -sum(c)
A = [ 2*c'  -1;
     -2*c'  -1 ];
b = [ Csum;
     -Csum ];

Aeq = []; beq = [];

%% ====== RISOLUZIONE ======
opts = optimoptions('intlinprog','Display','off');
[z, ~, exitflag] = intlinprog(f, intcon, A, b, Aeq, beq, lb, ub, opts);

if exitflag <= 0
    error("Ottimizzazione non riuscita (exitflag=%d). Controlla dati/vincoli.", exitflag);
end

x  = z(1:n);
x  = round(x);        % per stampa pulita (tolleranze numeriche)
x2 = 1 - x;

S1 = c.' * x;         % c*x
S2 = c.' * x2;        % c*x_negato = c*(1-x)

%% ====== STAMPA RICHIESTA ======
disp("x =");
disp(x');

disp("chosen_PE =");
disp(x'+1);

fprintf("S1 = c'*x = %.10g\n", S1);
fprintf("S2 = c'*(1-x) = %.10g\n", S2);
fprintf("diff = |S1 - S2| = %.10g\n", abs(S1 - S2));

