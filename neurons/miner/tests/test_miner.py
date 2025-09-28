import unittest

import bittensor as bt
from prettytable import PrettyTable
class TestMiner(unittest.TestCase):

    def test_metagrash(self):
        me = bt.Metagraph(netuid=2, network='local')

        i = 0
        validator = me.validator_permit
        stake = me.stake
        vtrust = me.validator_trust
        trust = me.trust
        consensus = me.consensus
        incentive = me.incentive
        dividends = me.dividends
        emission = me.emission
        update = me.last_update
        alpha_stake = me.alpha_stake
        active = me.active
        table = PrettyTable(["Active", "UID", "TYPE", "Stake Weight", "VTrust", "Trust", "Consensus", "Incentive", "Dividends", "Emission", "Updated", "Axon", "Port", "HotKey", "ColdKey", "AlphaStake"])
        for axon in me.axons:
            type = "Miner"
            if validator[i] :
                type = "Validator"

            table.add_row([active[i], i, type, stake[i], vtrust[i], trust[i], consensus[i], incentive[i], dividends[i], emission[i], update[i], axon.ip, axon.port, "", "", alpha_stake[i]])
            i = i + 1

        print(table)

        pass