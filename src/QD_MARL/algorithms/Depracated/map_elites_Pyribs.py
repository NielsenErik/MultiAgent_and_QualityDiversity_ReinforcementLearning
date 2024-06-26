#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
from cmath import inf
from tkinter import Grid
import numpy as np
from copy import deepcopy
from .common import OptMetaClass
from decisiontrees import Leaf, Condition
from operator import gt, lt, add, sub, mul
from processing_element import ProcessingElementFactory, PEFMetaClass
from ribs.archives._cvt_archive import CVTArchive
from ribs.archives._grid_archive import GridArchive
from ribs.archives._sliding_boundaries_archive import SlidingBoundariesArchive
from ribs.archives import EliteBatch, Elite
from ribs.archives._archive_data_frame import ArchiveDataFrame
from ribs.visualize import cvt_archive_heatmap
from ribs.visualize import grid_archive_heatmap
from ribs.visualize import sliding_boundaries_archive_heatmap
import matplotlib.pyplot as plt
from .individuals import *



class MapElites_Pyribs(ProcessingElementFactory, metaclass=OptMetaClass):
    def __init__(self, **kwargs):

        """
        Initializes the algorithm

        :map_size: The size of the map
        :map_bounds: List of bounds
        :init_pop_size: number of initial solutions
        :maximize: Boolean indicating if is a maximization problem
        :batch_pop: Number of population generated for iteration
        :c_factory: The factory for the conditions
        :l_factory: The factory for the leaves
        :bounds: dictionary containing the bounds for the two factories.
            It should contain two keys: "condition" and "leaf".
            The values must contain the bounds
            (a dict with keys (type, min, max))
            for all the parameters returned
            by "get_trainable_parameters"
        :max_depth: Maximum depth for the trees

        """
        self._log_path = kwargs["log_path"]
        self._map_size = kwargs["map_size"]
        self._map_bound = kwargs["map_bounds"]
        self._cx_prob = kwargs["cx_prob"] if "cx_prob" in kwargs else 0
        self._init_pop_size = kwargs["init_pop_size"]
        self._batch_pop = kwargs["batch_pop"]
        self._maximize = kwargs["maximize"]
        if not len(self._map_bound) == len(self._map_size):
            raise Exception("number of bound must match number of dimension")

        self._c_factory = kwargs["c_factory"]
        self._l_factory = kwargs["l_factory"]
        self._bounds = kwargs["bounds"]
        self._max_depth = kwargs["max_depth"]
        self._cond_depth = kwargs.get("cond_depth", 2)
        self._pop = []
        self._archive_type = kwargs["archive"]
        self._bins = kwargs["bins"]
        self._bins_sliding = kwargs["sliding_bins"]
        self._solution_dim = kwargs["solution_dim"]
        if self._archive_type == "CVT":
            self._archive = CVTArchive(self._bins,self._map_bound)
        elif self._archive_type == "Grid":
            self._archive = GridArchive(solution_dim=self._solution_dim, dims=self._map_size, ranges=self._map_bound)
        elif self._archive_type == "SlidingBoundaries":
            self._archive = SlidingBoundariesArchive(self._bins_sliding,self._map_bound)
        else:
            raise Exception("archive not valid")
        self._counter = 1 # number inserted in sol field of the archive
        self._gen_number = 1
        self._max_fitness = -inf
        self._selection_type = self.set_selection_type(kwargs["selection_type"])
        
    def _random_var(self):
        index = np.random.randint(0, self._bounds["input_index"]["max"])
        return GPVar(index)

    def _random_const(self):
        index = np.random.uniform(self._bounds["float"]["min"], self._bounds["float"]["max"])
        return GPConst(index)

    def _random_expr(self, depth=0):
        if depth < self._cond_depth - 1:
            type_ = np.random.randint(0, 3)
        else:
            type_ = np.random.randint(0, 2)

        if type_ == 0:
            return self._random_var()
        elif type_ == 1:
            return self._random_const()
        else:
            l = self._random_expr(depth + 1)
            r = self._random_expr(depth + 1)
            op = np.random.choice([add, sub, mul, safediv])
            return GPArithNode(op, l, r)

    def _random_condition(self):
        left = self._random_expr()
        right = self._random_expr()
        while isinstance(left, GPConst) and isinstance(right, GPConst):
            left = self._random_expr()
            right = self._random_expr()

        op = np.random.choice([gt, lt])

        return GPNodeIf(GPNodeCondition(op, left, right), None, None)

    def _random_leaf(self):
        tp = self._l_factory.get_trainable_parameters()

        if len(tp) == 0:
            return self._l_factory.create()
        else:
            params = []

            for param in tp:
                min_ = self._bounds[param]["min"]
                max_ = self._bounds[param]["max"]
                if self._bounds[param]["type"] == "int":
                    params.append(np.random.randint(min_, max_))
                elif self._bounds[param]["type"] == "float":
                    params.append(np.random.uniform(min_, max_))
                else:
                    raise ValueError("Unknown type")

            return self._l_factory.create(*params)

    def _get_random_leaf_or_condition(self):
        if np.random.uniform() < 0.5:
            return self._random_leaf()
        return self._random_condition()

    def _get_depth(self, node):
        """BFS search"""
        fringe = [(0, node)]
        max_ = 0
        while len(fringe) > 0:
            d, n = fringe.pop(0)
            if isinstance(node, Leaf) or \
                    isinstance(node, GPNodeCondition) or \
                    isinstance(node, GPExpr) or \
                    n is None:
                continue

            if d > max_:
                max_ = d

            if not isinstance(n, Leaf):
                fringe.append((d + 1, n._then))
                fringe.append((d + 1, n._else))
        return max_

    def _reduce_expr_len(self, expr):
        fringe = [(0, expr)]

        max_ = 0
        while len(fringe) > 0:
            d, cur = fringe.pop(0)
            if isinstance(cur, GPArithNode):
                if d + 1 > self._cond_depth:
                    cur.set_left(self._random_expr(d + 1))
                    cur.set_right(self._random_expr(d + 1))
                else:
                    fringe.append((d + 1, cur.get_left()))
                    fringe.append((d + 1, cur.get_right()))
                #print(d)
        return expr

    def _count_expr_len(self, expr):
        fringe = [(0, expr)]

        max_ = 0
        while len(fringe) > 0:
            d, cur = fringe.pop(0)
            if isinstance(cur, GPArithNode):
                fringe.append((d + 1, cur.get_left()))
                fringe.append((d + 1, cur.get_right()))
            if d > max_:
                max_=d
        return max_


    def _get_cond_depth(self, root):
        """BFS search"""

        fringe = [root]
        max_ = 0
        cc = 1
        while len(fringe) > 0:
            cur = fringe.pop(0)
            cc += 1
            if isinstance(cur, GPNodeIf):
                cond = cur._condition
                a = self._count_expr_len(cond.get_left())
                b = self._count_expr_len(cond.get_right())
                d = max(a,b )
                max_ = max(d, max_)
                fringe.append(cur.get_then())
                fringe.append(cur.get_else())
        return max_

    def _limit_cond_depth(self, root):
        """
        Limits the depth of the tree
        """
        fringe = [root]
        while len(fringe) > 0:
            cur = fringe.pop(0)

            if isinstance(cur, GPNodeIf):
                cond = cur._condition

                cond.set_left(self._reduce_expr_len(cond.get_left()))
                cond.set_right(self._reduce_expr_len(cond.get_right()))

                fringe.append(cur.get_then())
                fringe.append(cur.get_else())
        return root

    def _limit_depth(self, root):
        """
        Limits the depth of the tree
        """
        fringe = [(0, root)]

        while len(fringe) > 0:
            d, cur = fringe.pop(0)

            if isinstance(cur, GPNodeIf):
                if d + 1 == self._max_depth:
                    cur.set_then(self._random_leaf())
                    cur.set_else(self._random_leaf())
                fringe.append((d + 1, cur.get_left()))
                fringe.append((d + 1, cur.get_right()))
        return root

    def _get_descriptor(self, ind):
        return self._get_depth(ind), self._get_cond_depth(ind)
    
    def get_all_pop(self):
        df = self._archive.as_pandas(include_metadata=True)
        dict_to_return = dict()
        for elite in df.iterelites():
            dict_to_return[(int(elite[2][0]),int(elite[2][1]))] = (elite[4]._genes,elite[1])
        return dict_to_return.items()

    def _init_pop(self):
        pop = []
        grow = self._init_pop_size

        for i in range(grow):
            root = self._get_random_leaf_or_condition()
            fringe = [root]

            while len(fringe) > 0:
                node = fringe.pop(0)

                if isinstance(node, Leaf):
                    continue

                if self._get_depth(root) < self._max_depth - 1:
                    left = self._get_random_leaf_or_condition()
                    right = self._get_random_leaf_or_condition()
                else:
                    left = self._random_leaf()
                    right = self._random_leaf()

                node.set_then(left)
                node.set_else(right)

                fringe.append(left)
                fringe.append(right)
            
            pop.append(IndividualGP(root))
            self._pop = pop
        return pop

    def _mutation(self, p):
        p1 = p.deep_copy()._genes
        #print(type(p1))
        cp1 = None

        p1nodes = [(None, None, p1)]

        fringe = [IndividualGP(p1)]
        while len(fringe) > 0:
            node = fringe.pop(0)
            if not isinstance(node, Leaf) and not isinstance(node, IndividualGP):
                fringe.append(node.get_left())
                fringe.append(node.get_right())

                p1nodes.append((node, True, node.get_left()))
                p1nodes.append((node, False, node.get_right()))

        cp1 = np.random.randint(0, len(p1nodes))

        parent = IndividualGP(p1nodes[cp1][0])
        old_node = IndividualGP(p1nodes[cp1][2])
        if not isinstance(old_node, GPNodeCondition) or \
                not isinstance(old_node, GPExpr):
            new_node = self._get_random_leaf_or_condition()
        else:
            new_node = self._random_expr()

        if not isinstance(new_node, Leaf) and \
                not isinstance(new_node, GPExpr) and \
                    not isinstance(new_node, IndividualGP):
            if not isinstance(old_node, Leaf) and \
                    not isinstance(old_node, IndividualGP):
                new_node.set_then(old_node.get_left())
                new_node.set_else(old_node.get_right())
            else:
                new_node.set_then(self._random_leaf())
                new_node.set_else(self._random_leaf())

        if p1nodes[cp1][1] is not None:
            if p1nodes[cp1][1]:
                parent.set_then(new_node)
            else:
                parent.set_else(new_node)
        else:
            p1 = new_node
        p1 = self._limit_depth(p1)
        p1 = self._limit_cond_depth(p1)
        return IndividualGP(p1)


    def _crossover(self, par1, par2):
        p1, p2 = par1.copy()._genes, par2.copy()._genes
        cp1 = None
        cp2 = None
        p1, p2 = IndividualGP(p1), IndividualGP(p2)
        p1nodes = [(None, None, p1)]

        fringe = [p1]
        while len(fringe) > 0:
            node = fringe.pop(0)

            if not isinstance(node, Leaf) and not isinstance(node, IndividualGP) and not isinstance(node, Elite):
                fringe.append(node.get_left())
                fringe.append(node.get_right())

                p1nodes.append((node, True, node.get_left()))
                p1nodes.append((node, False, node.get_right()))

        cp1 = np.random.randint(0, len(p1nodes))
        st1 = p1nodes[cp1][2]

        p2nodes = [(None, None, p2)]

        fringe = [p2]
        while len(fringe) > 0:
            node = fringe.pop(0)
            if not isinstance(node, Leaf) and \
               not isinstance(node, GPVar) and \
               not isinstance(node, GPConst) and \
               not isinstance(node, IndividualGP) and \
               not isinstance(node, EliteBatch):
                fringe.append(node.get_left())
                fringe.append(node.get_right())

                if type(node.get_left()) == type(st1):
                    p2nodes.append((node, True, node.get_left()))
                if type(node.get_right()) == type(st1):
                    p2nodes.append((node, False, node.get_right()))

        cp2 = np.random.randint(0, len(p2nodes))

        st2 = p2nodes[cp2][2]

        if cp1 != 0:
            if p1nodes[cp1][1]:
                p1nodes[cp1][0].set_then(st2)
            else:
                p1nodes[cp1][0].set_else(st2)
        else:
            p1 = st2

        if cp2 != 0:
            if p2nodes[cp2][1]:
                p2nodes[cp2][0].set_then(st1)
            else:
                p2nodes[cp2][0].set_else(st1)
        else:
            p2 = st1
            
        return IndividualGP(p1), IndividualGP(p2)
    
    def set_selection_type(self, selection_type = 'random'):
        return selection_type
    
    def set_pop_selection(self, coach_index = None):
        if self._selection_type == "random":
            self._pop = [
                IndividualGP(self._archive.sample_elites(1)) #metadata
                for _ in range(self._batch_pop)
            ]
        elif self._selection_type == "best":
            self._pop = [
                IndividualGP(self._archive.best_elite) #metadata
                for _ in range(self._batch_pop)
            ]
        elif self._selection_type == "coach":
            if coach_index is None:
                raise Exception("coach index not valid")
            team_index = self._archive.int_to_grid_index(coach_index)
            self._pop = [
                IndividualGP(self._archive.retrieve_single(individual)) #metadata
                for individual in team_index
            ]
        else:
            raise Exception("selection type not valid")
        return [p._genes for p in self._pop]
    
    def ask(self, coach_index = None):
        self._pop = []
        if self._archive.empty:
            self._pop = self._init_pop()
        else:
            temp = list()
            self._pop = self.set_pop_selection(coach_index = coach_index)
            for i in range(0, len(self._pop), 2):
                p1 = IndividualGP(self._pop[i])
                
                if i + 1 < len(self._pop):
                    p2 = IndividualGP(self._pop[i + 1])
                else:
                    p2 = None
                o1, o2 = None, None
                
                # Crossover
                if p2 is not None:
                    if  np.random.uniform() < self._cx_prob:
                        o1, o2 = self._crossover(p1, p2)
                        temp.append(o1)
                        temp.append(o2)
                    else:
                        temp.append(p1)
                        temp.append(p2)
                else:
                    temp.append(p1)
            self._pop = [self._mutation(p) for p in temp]
        return [p._genes for p in self._pop]
    
    def tell(self,fitnesses,data=None):
        
        for p in zip(self._pop,fitnesses):
            desc = self._get_descriptor(p[0]._genes)
            p[0]._fitness = p[1]
            thr = [abs((max(self._map_bound[i]) - min(self._map_bound[i])) / self._map_size[i]) for i in
                range(len(self._map_size))]
            desc = [int((desc[i] - min(self._map_bound[i])) / thr[i]) for i in range(len(self._map_size))]
            for i in range(len(self._map_size)):
                if desc[i] < 0:
                    desc[i] = 0
                elif desc[i] >= self._map_size[i]:
                    desc[i] = self._map_size[i] - 1
            desc = tuple(desc)
            status, value = self._archive.add_single(desc, p[1], desc, self._counter)
            #print(status, value)
            self._counter += 1
        
        #Visualize archives 
        if max(fitnesses) > self._max_fitness:
            self._max_fitness = max(fitnesses)
            print_info("New best at generation: ",self._gen_number-1, " fitness: ",max(fitnesses))
        if self._gen_number%5 == 0 :
            plt.figure(figsize=(8, 6))
            if self._archive_type == "CVT":
                cvt_archive_heatmap(self._archive,vmin=-200,vmax=-100)
            elif self._archive_type == "Grid":
                grid_archive_heatmap(self._archive,vmin=-200,vmax=-100)
            elif self._archive_type == "SlidingBoundaries":
                sliding_boundaries_archive_heatmap(self._archive,vmin=0,vmax=500)
            else:
                raise Exception("archive not valid")
            
            if self._log_path is not None:
                plt.ylabel("Condition Depth")
                plt.xlabel("Depth")
                plt.title("Map Elites Archive Depth at Generation: "+str(self._gen_number))
                os.makedirs(os.path.join(self._log_path, "archives_depth"), exist_ok=True)
                saving_path = os.path.join(self._log_path, "archives_depth/archive_depth_at_gen_"+str(self._gen_number)+".png")
                plt.savefig(saving_path)
                plt.close()
        self._gen_number += 1
        
        