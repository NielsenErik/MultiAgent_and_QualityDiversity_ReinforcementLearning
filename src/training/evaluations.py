import os
import sys

sys.path.append(".")
import random
import time
from copy import deepcopy
from math import sqrt

import numpy as np
import pettingzoo

# from memory_profiler import profile
import training.differentObservations as differentObservations
from agents.agents import *
from algorithms import (
    individuals,
    map_elites_Pyribs,
    mapElitesCMA_pyRibs,
)
from decisiontrees import (
    ConditionFactory,
    DecisionTree,
    QLearningLeafFactory,
    RLDecisionTree,
)
from magent2.environments import battle_v4, battlefield_v5
from pettingzoo.utils import aec_to_parallel, parallel_to_aec
from utils import *



def evaluate(trees, config):
    
    # Check whether the phenotype is valid
    for tree in trees:
        if tree is None:
            return -10**3, None
    tot_logs = os.path.join(config["log_path"], "eval_log", str(config['generation']))
    os.makedirs(tot_logs, exist_ok=True)
    # Re-import the environments here to avoid problems with parallelization
    import training.differentObservations as differentObservations
    #from manual_policies import Policies
    import numpy as np
    from magent2.environments import battlefield_v5
    # Load the function used to computer the features from the observation
    compute_features = getattr(differentObservations, f"compute_features_{config['observation']}")

    # Load manual policy if present
    policy = None
    #if config['manual_policy']:
    #    policy = Policies(config['manual_policy'])

    # Load the environment
    env = battlefield_v5.env(**config['environment'])
    env.reset()

    # Set tree and policy to agents
    agents = {}
    for agent_name in env.agents:
        agent_squad = "_".join(agent_name.split("_")[:-1])
        if agent_squad == config["team_to_optimize"]:
            agent_number = int("_".join(agent_name.split("_")[1]))
            index = agent_number - 1
        # This is to handle the case in which the agents are divided in sets
        # used for the baseline experiments
            if "sets" in config:
                for set_index in range(len(config["sets"])):
                    if agent_number in config["sets"][set_index]:
                        index = set_index

            # Initialize trining agent
            agents[agent_name] = Agent(agent_name, agent_squad, None, trees[index], None, True)
        else:
            # Initialize random or policy agent
            agents[agent_name] = Agent(agent_name, agent_squad, None, None, policy, False)

    # Start the training
    kills = []
    completed = []
    for i in range(config["training"]["episodes"]):
        kills.append(0)
        episode_rew = []
        completed.append(0)
        # Seed the environment
        env.reset(seed=i)
        np.random.seed(i)
        env.reset()

        # Set variabler for new episode
        for agent_name in agents:
            if agents[agent_name].to_optimize():
                agents[agent_name].new_episode()
        red_agents = 12
        blue_agents = 12
        
        # tree.empty_buffers()    # NO-BUFFER LEAFS
        # Iterate over all the agents
        for index, agent_name in enumerate(env.agent_iter()):

            obs, rew, done, trunc, _ = env.last()

            agent = agents[agent_name]

            if agent.to_optimize():
                # Register the reward
                agent.set_reward(rew)
            
            action = None
            if not done and not trunc: # if the agent is alive
                if agent.to_optimize():
                    # compute_features(observation, allies, enemies)
                    if agent.get_squad() == 'blue':
                        action = agent.get_output(compute_features(obs, blue_agents, red_agents))
                    else:
                        action = agent.get_output(compute_features(obs, red_agents, blue_agents))
                else:
                    if agent.has_policy():
                        if agent.get_squad() == 'blue':
                            action = agent.get_output(compute_features(obs, blue_agents, red_agents))
                        else:
                            action = agent.get_output(compute_features(obs, red_agents, blue_agents))
                    else:
                        #action = env.action_space(agent_name).sample()
                        action = np.random.randint(21)
            else: # update the number of active agents
                if agent.get_squad() == 'red':
                    red_agents -= 1
                    if done:
                        kills[-1] += 1
                        if red_agents == 0:
                            completed[-1] = 1
                else:
                    blue_agents -= 1

            env.step(action)

    env.close()
    avg_kills = np.mean(kills)
    kills.insert(0,avg_kills)
    # Log the kills in each episode
    with open(os.path.join(tot_logs, "log_kills.txt"), "a") as f:
        f.write(str(kills) + "\n")
    f.close()
    # Log the rewards in each episode

    completed.insert(0, np.sum(completed))
    # Log the completion of each episode
    with open(os.path.join(tot_logs, "log_completed.txt"), "a") as f:
        f.write(str(completed) + "\n")
    f.close()





    scores = []
    actual_trees = []
    for agent_name in agents:
        if agents[agent_name].to_optimize():
            scores.append(agents[agent_name].get_score_statistics(config['statistics']['agent']))
            actual_trees.append(agents[agent_name].get_tree())
    rewards = scores
    rewards.insert(0, np.mean(rewards))
    # Log the rewards in each episode
    with open(os.path.join(tot_logs, "log_rewards.txt"), "a") as f:
        f.write(str(rewards) + "\n")
    f.close()

    return scores, actual_trees