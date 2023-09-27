#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
    dt.tree
    ~~~~~~~

    This module implements a decision tree

    :copyright: (c) 2021 by Leonardo Lucio Custode.
    :license: MIT, see LICENSE for more details.
"""
from .nodes import Node
from .leaves import Leaf
from collections import deque
from .conditions import Condition


class DecisionTree:
    """
    This class implements a general decision tree.
    It can be used for classification/regression tasks.
    """

    def __init__(self, root):
        """
        Initializes the decision tree

        :root: The root of the tree, must be of type Node.
        """
        self._root = root

    def get_root(self):
        return self._root

    def set_root(self, value):
        self._root = value

    def get_output(self, input_):
        """
        Computes the output of the decision tree

        :input_: An input vector
        :returns: A numpy array, with size equal to the
                    dimensionality of the output space

        """
        return self._root.get_output(input_)

    def empty_buffers(self):
        """
        Resets the buffers of all the nodes in the tree
        """
        self._root.empty_buffers()

    def get_leaves(self):
        """
        Returns the leaves of the tree
        :returns: A Leaf object
        """
        fringe = [self._root]
        leaves = []
        while len(fringe) > 0:
            node = fringe.pop(0)
            if isinstance(node, Leaf):
                leaves.append(node)
            else:
                fringe.append(node.get_left())
                fringe.append(node.get_right())
        return leaves

    def replace(self, old_node, new_node):
        """
        Replaces a node of the tree with another node.
        If the tree does not contain the node, the tree remains unchanged.

        :old_node: The node to replace
        :new_node: The node that replaces the old one
        """
        fringe = [(self._root, None)]  # (node, parent)

        while len(fringe) > 0:
            node, parent = fringe.pop(0)
            if node is old_node:
                if parent is not None:
                    is_left = parent.get_left() == node
                    if is_left:
                        parent.set_left(new_node)
                    else:
                        parent.set_right(new_node)
                else:
                    self._root = new_node
            else:
                if not isinstance(node, Leaf):
                    fringe.append((node.get_left(), node))
                    fringe.append((node.get_right(), node))

    def __repr__(self):
        fringe = [(self._root, None)]
        string = ""

        while len(fringe) > 0:
            cur, par = fringe.pop(0)

            string += f"{id(cur)} [{str(cur)}]\n"
            if par is not None:
                branch = "True" if par._left is cur else "False"
                string += f"{id(par)} -->|{branch}| {id(cur)}\n"
            if not isinstance(cur, Leaf):
                fringe.append((cur.get_left(), cur))
                fringe.append((cur.get_right(), cur))

        return string

    def __str__(self):
        return repr(self)

    def copy(self):
        """
        Returns a copy
        """
        dt = DecisionTree(self.get_root().copy())
        return dt


class RLDecisionTree(DecisionTree):
    """
    A Decision tree that can perform RL task
    """

    def __init__(self, root, gamma, lambda_=0.0):
        """
        Initializes the decision tree for RL tasks

        :root: The root of the tree
        :gamma: The discount factor
        """
        DecisionTree.__init__(self, root)
        self._gamma = gamma
        self._lambda = lambda_
        self._last_leaves = deque(maxlen=2)
        self._rewards = deque(maxlen=2)

    def get_output(self, input_):
        """
        Computes the output of the decision tree

        :input_: An input vector
        :returns: A numpy array, with size equal to the
                    dimensionality of the output space
        """
        decision = self._root
        while isinstance(decision, Node):
            if isinstance(decision, Leaf):
                self._last_leaves.appendleft(decision)
                decision = decision.get_output(input_)
            else:
                branch = decision.get_branch(input_)
                if branch == Condition.BRANCH_LEFT:
                    decision = decision.get_left()
                else:
                    decision = decision.get_right()
        return decision

    def set_reward(self, reward):
        """
        Gives a reward to the tree.
        NOTE: this method stores the last reward and makes
        the tree "learn" the penultimate reward.
        To make the tree "learn" from the last reward, use
        set_reward_end_of_episode().

        :reward: The reward obtained by the environment
        """
        self._rewards.appendleft(reward)
        if len(self._last_leaves) == 2:
            leaf = self._last_leaves.pop()
            leaf.set_reward(self._rewards.pop() +
                            self._gamma * self._last_leaves[0].get_value())

    def set_reward_end_of_episode(self):
        """
        Sets the reward to the last leaf visited in the episode.
        """
        assert len(self._last_leaves) == 1, \
            "This method has to be called at the end of an episode"
        leaf = self._last_leaves.pop()
        leaf.set_reward(self._rewards.pop())

    def empty_buffers(self):
        """
        Resets the buffers of all the nodes in the tree
        """
        self._last_leaves = deque(maxlen=2)
        self._rewards = deque(maxlen=2)
        self._root.empty_buffers()

    def force_action(self, input_, action):
        """
        Forces the tree to take an action

        :input_: the input of the tree
        :action: the action to be forced
        """
        decision = self._root
        while isinstance(decision, Node):
            if isinstance(decision, Leaf):
                self._last_leaves.appendleft(decision)
                decision.force_action(input_, action)
                decision = None
            else:
                branch = decision.get_branch(input_)
                if branch == Condition.BRANCH_LEFT:
                    decision = decision.get_left()
                else:
                    decision = decision.get_right()
        return action
