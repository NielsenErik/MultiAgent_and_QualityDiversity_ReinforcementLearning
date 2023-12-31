#!/usr/bin/python3
"""
Implementation of the grammatical evolution

Author: Leonardo Lucio Custode
Creation Date: 04-04-2020
Last modified: mer 6 mag 2020, 16:30:41
"""
import os
import re
import string
from abc import abstractmethod
from typing import List

import numpy as np

TAB = " " * 4


class GrammaticalEvolutionTranslator:
    def __init__(self, grammar):
        """
        Initializes a new instance of the Grammatical Evolution
        :param n_inputs: the number of inputs of the program
        :param leaf: the leaf that can be used - a constructor
        :param constant_range: A list of constants that can be used - default is a list of integers between -10 and 10
        """
        self.operators = grammar

    def _find_candidates(self, string):
        return re.findall("<[^> ]+>", string)

    def _find_replacement(self, candidate, gene):
        key = candidate.replace("<", "").replace(">", "")
        value = self.operators[key][gene % len(self.operators[key])]
        return value

    def genotype_to_str(self, genotype):
        """ This method translates a genotype into an executable program (python) """
        string = "<bt>"
        candidates = [None]
        ctr = 0
        _max_trials = 1
        genes_used = 0

        # Generate phenotype starting from the genotype
        #   If the individual runs out of genes, it restarts from the beginning, as suggested by Ryan et al 1998
        while len(candidates) > 0 and ctr <= _max_trials:
            if ctr == _max_trials:
                return "", len(genotype)
            for gene in genotype:
                candidates = self._find_candidates(string)
                if len(candidates) > 0:
                    value = self._find_replacement(candidates[0], gene)
                    string = string.replace(candidates[0], value, 1)
                    genes_used += 1
                else:
                    break
            ctr += 1

        string = self._fix_indentation(string)
        return string, genes_used

    def _fix_indentation(self, string):
        # If parenthesis are present in the outermost block, remove them
        if string[0] == "{":
            string = string[1:-1]

        # Split in lines
        string = string.replace(";", "\n")
        string = string.replace("{", "{\n")
        string = string.replace("}", "}\n")
        lines = string.split("\n")

        fixed_lines = []
        n_tabs = 0

        # Fix lines
        for line in lines:
            if len(line) > 0:
                fixed_lines.append(TAB * n_tabs + line.replace("{", "").replace("}", ""))

                if line[-1] == "{":
                    n_tabs += 1
                while len(line) > 0 and line[-1] == "}":
                    n_tabs -= 1
                    line = line[:-1]
                if n_tabs >= 100:
                    return "None"

        return "\n".join(fixed_lines)


class Individual:
    """Represents an individual."""

    def __init__(self, genes, fitness=None, parents=None):
        """Initializes a new individual

        :genes: a list of genes
        :fitness: the fitness for the individual. Default: None.

        """
        self._genes = np.array(genes)
        self._fitness = fitness
        self._parents = parents  # A list containing the indices of the parents in the previous population
        self._id = "".join(np.random.choice([*string.ascii_lowercase], 10))

    def get_genes(self):
        return self._genes

    def __repr__(self):
        return repr(self._genes).replace("array(", "").replace(")", "").replace("\n", "") + "; Fitness: {}; Parents: {}".format(self._fitness, self._parents)

    def __str__(self):
        return repr(self)

    def __eq__(self, other):
        return sum(self._genes != other._genes) == 0

    def copy(self):
        return Individual(self._genes[:], self._fitness, self._parents[:] if self._parents is not None else None)

    def __hash__(self):
        return hash(self._id)


class Mutator:
    """Interface for the mutation operators"""

    @abstractmethod
    def __call__(self, individual):
        pass


class UniformMutator(Mutator):
    """Uniform mutation"""

    def __init__(self, gene_probability, max_value):
        """Initializes the mutator

        :gene_probability: The probability of mutation of a single gene
        :max_value: The maximum value for a gene

        """
        Mutator.__init__(self)

        self._gene_probability = gene_probability
        self._max_value = max_value

    def __call__(self, individual):
        mutated_genes = np.random.uniform(0, 1, len(individual._genes)) < self._gene_probability
        gene_values = np.random.randint(0, self._max_value, sum(mutated_genes))
        genes = individual._genes.copy()
        genes[mutated_genes] = gene_values
        new_individual = Individual(genes, parents=individual._parents)
        return new_individual

    def __repr__(self):
        return "UniformMutator({}, {})".format(self._gene_probability, self._max_value)


class Crossover:
    """Interface for the crossover operators"""

    @abstractmethod
    def __call__(self, individual1, individual2) -> List:
        pass


class OnePointCrossover(Crossover):
    """One point crossover"""

    def __call__(self, individual1, individual2):
        point = np.random.randint(0, len(individual1._genes) - 2)

        new_individuals = [Individual([*individual1._genes[:point], *individual2._genes[point:]])]
        new_individuals.append(Individual([*individual2._genes[:point], *individual1._genes[point:]]))
        return new_individuals

    def __repr__(self):
        return "OnePointCrossover"


class Selection:
    """Abstract class for the selection operators"""

    def __init__(self, logfile=None):
        self._logfile = logfile

    @abstractmethod
    def __call__(self, fitnesses: List) -> List:
        """ Returns a sorted list of indices, so that one can simply crossover the adjacent individuals """
        pass

    def _log(self, msg):
        if self._logfile is not None:
            with open(self._logfile, "a") as f:
                f.write(msg + "\n")


class BestSelection(Selection):
    """Interface for the selection operators"""

    @abstractmethod
    def __call__(self, fitnesses: List) -> List:
        """ Returns a sorted list of indices, so that one can simply crossover the adjacent individuals """
        order = sorted(range(len(fitnesses)), key=lambda x: fitnesses[x], reverse=True)
        self._log("The individuals (Fitnesses {}) have been sorted as {}.".format(fitnesses, order))
        return order

    def __repr__(self):
        return "BestSelection"


class TournamentSelection(Selection):
    """Tournament selection"""

    def __init__(self, tournament_size, logfile=None):
        """Initializes a new tournament selection

        :tournament_size: number of individual in the tournament
        """
        Selection.__init__(self, logfile)

        self._tournament_size = tournament_size

    def __call__(self, fitnesses):
        tournaments = np.random.randint(0, len(fitnesses), (len(fitnesses), self._tournament_size))
        selection = []

        for i in tournaments:
            selection.append(i[np.argmax([fitnesses[j] for j in i])])
            self._log("Individuals in the tournament: {} (fitnesses: {}), selected: {}".format(list(i), [fitnesses[j] for j in i], selection[-1]))

        return selection

    def __repr__(self):
        return "TournamentSelection({})".format(self._tournament_size)


class Replacement:
    """ Interface for the replacement operators """

    @abstractmethod
    def __call__(self, old_pop: List, new_pop: List) -> List:
        pass


class NoReplacement(Replacement):
    """Uses the new population."""

    def __call__(self, old_pop, new_pop):
        return new_pop


class ReplaceIfBetter(Replacement):
    """Replaces the parents if the new individual is better"""

    def __init__(self, logfile=None):
        self._logfile = logfile

    def _log(self, msg):
        if self._logfile is not None:
            with open(self._logfile, "a") as f:
                f.write(msg + "\n")

    def __call__(self, old_pop, new_pop):
        final_population = {old: old.copy() for old in old_pop}
        assert len(final_population) == len(old_pop), f"Initially {len(final_population)} != {len(old_pop)}"
        assert len(final_population) == len(new_pop), f"Initially {len(final_population)} != {len(new_pop)}"

        for ind in new_pop:
            # Here I use final_population instead of directly the parents because
            # They may have already been replaced by someone else
            if ind._parents is None:
                continue
            parents_fitnesses = {p: final_population[p]._fitness for p in ind._parents}

            worst_fitness = float("inf")
            worst_parent = None

            for parent, fitness in parents_fitnesses.items():
                if fitness < worst_fitness:
                    worst_fitness = fitness
                    worst_parent = parent

            if ind._fitness >= worst_fitness:
                final_population[worst_parent] = ind

        final_population = list(final_population.values())
        assert len(final_population) == len(old_pop), f"{len(final_population)} != {len(old_pop)}"
        assert len(final_population) == len(new_pop), f"{len(final_population)} != {len(new_pop)}"
        return final_population

    def __repr__(self):
        return "ReplaceIfBetter"


class Replacement:
    """ Interface for the replacement operators """

    @abstractmethod
    def __call__(self, old_pop: List, new_pop: List) -> List:
        pass


class ReplaceWithOldIfWorse(Replacement):
    """Replaces the parents if the new individual is better"""

    def __init__(self, logfile=None):
        self._logfile = logfile

    def _log(self, msg):
        if self._logfile is not None:
            with open(self._logfile, "a") as f:
                f.write(msg + "\n")

    def __call__(self, old_pop, new_pop):
        final_pop = []

        for o in old_pop:
            o._parents = None

        for i in np.arange(0, len(new_pop), step=2):
            i1, i2 = new_pop[i:i + 2]
            if i1._parents is None:
                # First generation
                assert i2._parents is None
                final_pop.append(i1.copy())
                final_pop.append(i2.copy())
                continue

            if len(i1._parents) == 1:
                for ind in [i1, i2]:
                    parent = ind._parents[0]
                    if ind._fitness > parent._fitness:
                        final_pop.append(ind.copy())
                    else:
                        final_pop.append(parent.copy())
            else:
                p1, p2 = [k for k in i1._parents]
                fn1, fn2 = [k._fitness for k in [i1, i2]]
                fo1, fo2 = [k._fitness for k in [p1, p2]]

                newbest = max(fn1, fn2)
                newworst = min(fn1, fn2)
                oldbest = max(fo1, fo2)
                oldworst = min(fo1, fo2)

                if (newworst > oldbest) or (newbest > oldbest and newworst > oldworst):
                    final_pop.append(i1.copy())
                    final_pop.append(i2.copy())
                else:
                    if newbest < oldworst:
                        final_pop.append(p1.copy())
                        final_pop.append(p2.copy())
                    else:
                        if fn1 > fn2:
                            final_pop.append(i1.copy())
                        else:
                            final_pop.append(i2.copy())

                        if fo1 == oldbest:
                            final_pop.append(p1.copy())
                        else:
                            final_pop.append(p2.copy())

        assert len(final_pop) == len(old_pop) == len(new_pop)
        return final_pop

    def __repr__(self):
        return "ReplaceWithOldIfWorse"


class GrammaticalEvolution:
    """A class that implements grammatical evolution (Ryan et al. 1995)"""

    def __init__(self, pop_size, agents, sets, mutation, crossover, selection, replacement, mut_prob, cx_prob, genotype_length, max_int=10000, no_mig=False, individual_genes_injected=None, injection_rate = 0.0, logdir=None):
        """TODO: to be defined.

        :pop_size: the size of the population
        :mutation: the mutation operator
        :crossover: the crossover operator
        :selection: the selection operator
        :replacement: the replacement operator
        :mut_prob: the mutation probability
        :cx_prob: the crossover probability
        :genotype_length: the length of the genotype
        :max_int: the biggest constant that can be contained in the genotype (so random number in the range [0, max_int] are generated)

        """
        self._pop_size = pop_size # Pop dimension
        self._agents = agents # Number of agents
        self._sets = sets # Number of sets
        self._mutation = mutation # Mutation operator
        self._crossover = crossover # Crossover operator
        self._selection = selection # Selection operator
        self._replacement = replacement # Repalcement operator
        self._mut_prob = mut_prob # Mutation probability
        self._cx_prob = cx_prob # Crossover probability
        self._no_mig = no_mig   # flag no migration
        self._genotype_length = genotype_length
        self._individuals = [ [] for _ in range(self._sets)]
        self._max_int = max_int
        self._individual_genes_injected = individual_genes_injected    # inject manual policy
        self._injection_rate = injection_rate  # inject manual policy
        self._logdir = logdir if logdir is not None else None
        self._init_pop()
        if self._individual_genes_injected is not None:
            self._inject_individual(self._individual_genes_injected, self._injection_rate)
        self._old_individuals = [ [] for _ in range(self._sets)]
        self._updated = [False for _ in range(self._sets)]  # To detect the first generation

    def _init_pop(self):
        """Initializes the population"""
        for set_ in range(self._sets):
            for j in range(self._pop_size):
                self._individuals[set_].append(self._random_individual())
                self._log(set_, "INIT", "Individual {}:\n{}".format(j, self._individuals[set_][-1]))

    def _inject_individual(self, individual_genes, injection_rate):
        #assert len(individual_genes) == self._genotype_length, f"Manual individual genes lenght ({len(individual)}) is different from genotype_lenght ({self._genotype_lenght})."
        
        # Reshape the genes if necessary
        if (len(individual_genes) < self._genotype_length):
            # ones because one means leaf
            individual_genes = np.hstack([individual_genes, np.ones(self._genotype_length - len(individual_genes), dtype=int)])
        elif (len(individual_genes) > self._genotype_length):
            individual_genes = individual_genes[:self._genotype_length]
        
        individue_to_inject = Individual(individual_genes, None, None) # Create the individual with the genes injeceted
        for set_ in range(self._sets): # Inject the individual in each set with the same rate
            indexes = np.random.choice(self._pop_size, int(self._pop_size * injection_rate), replace=False)  # Extract random indexes
            for index in indexes:
                self._log(set_, "INJ", f"Individual {self._individuals[set_][index]} has been replaced with injected {individue_to_inject}")
                self._individuals[set_][index] = individue_to_inject.copy() # Replace selected individual with injected individual
		

    def _log(self, set_, tag, string): # CONTROLLARE CHE LA SCRITTURA AVVENGA CORRETTAMENTE
        if self._logdir is not None:
            with open(os.path.join(self._logdir, f"set_{set_}.log"), "a") as f:
                f.write("[{}] {}\n".format(tag, string))

    def _random_individual(self):
        """ Generates a random individual """
        return Individual(np.random.randint(0, self._max_int + 1, self._genotype_length))

    def ask(self):
        """ Returns the current population """
        for set_ in range(self._sets):
            self._old_individuals[set_] = self._individuals[set_][:]
            if self._updated[set_]:
                self._individuals[set_] = []
                _sorted_pop = [self._old_individuals[set_][j].copy() for j in self._selection([i._fitness for i in self._old_individuals[set_]])]

                for s in _sorted_pop:
                    s._parents = None

                self._log(set_, "POPULATION", "Sorted population:\n" + "\n".join("Individual {}:\n{}".format(srt_idx, _sorted_pop[srt_idx]) for srt_idx in range(len(_sorted_pop))))

                cx_random_numbers = np.random.uniform(0, 1, len(_sorted_pop)//2)
                m_random_numbers = np.random.uniform(0, 1, len(_sorted_pop))

                # Crossover
                for index, cxp in enumerate(cx_random_numbers):
                    ind1, ind2 = _sorted_pop[2 * index: 2 * index + 2]
                    if cxp < self._cx_prob:
                        self._log(set_, "CX", "cx happened between individual {} and {}".format(2 * index, 2 * index + 1))
                        self._individuals[set_].extend(self._crossover(ind1, ind2))
                        self._individuals[set_][-1]._parents = [ind1, ind2]
                        self._individuals[set_][-2]._parents = [ind1, ind2]
                        self._log(set_, "CX", "Individual {} has parents [{}, {}] (Fitness [{}, {}])".format(2 * index, 2 * index, 2 * index + 1, ind1._fitness, ind2._fitness))
                        self._log(set_, "CX", "Individual {} has parents [{}, {}] (Fitness [{}, {}])".format(2 * index + 1, 2 * index, 2 * index + 1, ind1._fitness, ind2._fitness))
                    else:
                        self._log(set_, "CX", "cx did not happen between individual {} and {}".format(2 * index, 2 * index + 1))
                        self._individuals[set_].extend([Individual(ind1._genes), Individual(ind2._genes)])
                        self._individuals[set_][-1]._parents = [ind2]
                        self._individuals[set_][-2]._parents = [ind1]
                        self._log(set_, "CX", "Individual {} has parents [{}] (Fitness {})".format(2 * index, 2 * index, ind1._fitness))
                        self._log(set_, "CX", "Individual {} has parents [{}] (Fitness {})".format(2 * index + 1, 2 * index + 1, ind2._fitness))

                if len(_sorted_pop) % 2 == 1:
                    self._individuals[set_].append(_sorted_pop[-1])
                    self._individuals[set_][-1]._parents = [_sorted_pop[-1]]

                # Mutation
                for i, mp in enumerate(m_random_numbers):
                    if mp < self._mut_prob:
                        self._log(set_, "MUT", "Mutation occurred for individual {}".format(i))
                    self._individuals[set_][i] = self._mutation(self._individuals[set_][i])
                self._old_individuals[set_] = _sorted_pop

        # Migration and adoption
        if not self._no_mig and all(self._updated):
            random_set = np.random.randint(self._sets)
            best = None
            best_fitness = -float("inf")
            for i in self._old_individuals[random_set]:
                if best_fitness < i._fitness:
                    best_fitness = i._fitness
                    best = i.copy()
            best._fitness = None
            best._parents = None
            self._log(random_set, "MIG", "Individual {} migrate".format(best))

            for set_ in range(self._sets):
                if set_ != random_set:
                    random_index = np.random.randint(self._pop_size)
                    old_ind = self._individuals[set_][random_index]
                    new_ind = best.copy()
                    new_ind._parents = [p.copy() for p in old_ind._parents]
                    self._individuals[set_][random_index] = new_ind
                    self._log(set_, "MIG", "Individual {} replaced with {}".format(old_ind, self._individuals[set_][random_index]))
        # Migration and adoption

        return self._individuals

    def tell(self, fitnesses):
        """
        Assigns the fitness for each individual

        :squad_fitnesses: [agents x pop_size] list of numbers (the higher the better) associated (by index) to the individuals
                          Must be orginezed in [agents x pop_size] before the call of this function
        """

        for set_ in range(self._sets):
            for index, (i, f) in enumerate(zip(self._individuals[set_], fitnesses[set_])):
                if i._parents is not None:
                    self._log(set_, "FITNESS", "Individual {} has fitness {}. Its parents ({}) have fitnesses {}".format(index, f, i._parents, [k._fitness for k in i._parents]))
                else:
                    self._log(set_, "FITNESS", "Individual {} has fitness {}".format(index, f))
                i._fitness = f
            self._update_population(set_)

    def _update_population(self, set_):
        """ Creates the next population """
        self._updated[set_] = True
        self._individuals[set_] = self._replacement(self._old_individuals[set_], self._individuals[set_])
