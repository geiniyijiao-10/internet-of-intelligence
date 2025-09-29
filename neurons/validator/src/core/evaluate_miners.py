# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2023 Internet Of Intelligence

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import time
import bittensor as bt
import numpy as np
import neurons.validator.src.config.const as conf
from pathlib import Path

from typing import List, Dict, Any
from neurons.base.neuron import BaseNeuron
from neurons.base.protocol import AIAgentProtocol
from neurons.utils.uids import get_random_uids
from neurons.utils.encrypt import generate_nonce, verify, read_public_key

class EvaluateMiners:
    _validator = None
    miner_scores = {}
    miners: list[bt.NeuronInfo] = []

    def __init__(self, validator:BaseNeuron):
        self._validator = validator
        self.miner_scores = {}

    async def start(self):
        miner_uids = get_random_uids(self._validator, k=self._validator.config.neuron.sample_size)

        responses = await self.get_server_config(miner_uids)

        rewards = self.get_rewards(responses=responses)

        bt.logging.info(f"[evaluate_miners][forward] Scored responses: miner_uids:{miner_uids} rewards:{rewards}")
        self._validator.update_scores(rewards, miner_uids)
        time.sleep(60)

    async def get_server_config(self, miner_uids:np.ndarray):
        nonce = generate_nonce()
        synapse = {
            'url': 'http://127.0.0.1:8000/v1/agent/miner',
            'method': 'config',
            'params': {
                'nonce': nonce,
            }
        }
        bt.logging.trace(f"[evaluate_miners][forward] start miner uids:{miner_uids} synapse:{synapse}")

        responses = await self._validator.dendrite(
            axons=[self._validator.metagraph.axons[uid] for uid in miner_uids],
            synapse=AIAgentProtocol(input=synapse),
            deserialize=True,
        )
        bt.logging.trace(f"[evaluate_miners][forward] received responses: {responses}")

        valid_results = []
        now_ts = int(time.time() * 1000)
        pub_key_path = Path(__file__).resolve().parent.parent / "config" / "public.key"
        pub_key = read_public_key(pub_key_path)

        for res in responses:

            if res == None:
                valid_results.append(None)
                continue

            out = res.output
            if not out.get("status", False):
                valid_results.append(None)
                continue

            data = out.get("data", {})

            if data.get("nonce") != nonce:
                valid_results.append(None)
                continue

            signature = data.get("signature")
            if not signature or not verify(data, signature, pub_key):
                valid_results.append(None)
                continue

            ts = data.get("timestamp", 0)
            if now_ts - ts > 10_000:
                valid_results.append(None)
                continue

            valid_results.append({
                "containers": data.get("containers", []),
                "gpu": data.get("gpu", []),
                "ip": data.get("ip")
            })

        bt.logging.info(f"[evaluate_miners][forward] valid results: {valid_results}")

        return valid_results

    def get_rewards(
            self,
            responses: List[Dict[str, Any] | None],
    ) -> np.ndarray:
        # Precompute totals for normalization
        total_gpus = sum(len(r["gpu"]) for r in responses if r is not None)
        total_uptime = sum(
            sum(c["uptime"] for c in r["containers"] if c["status"] == 1)
            for r in responses if r is not None
        )

        scores = []
        for r in responses:
            if r is None:
                scores.append(0.0)
                continue

            # Score A: GPU count normalized
            score_a = len(r["gpu"]) / total_gpus if total_gpus > 0 else 0

            # Score B: containers uptime
            score_b = sum(c["uptime"] for c in r["containers"] if c["status"] == 1)
            score_b = score_b / total_uptime if total_uptime > 0 else 0

            # Score C: average uptime bonus > 7 days (~604800s)
            score_c = 0.0
            valid_uptimes = [c["uptime"] for c in r["containers"] if c["status"] == 1]
            if valid_uptimes:
                avg_container_uptime = sum(valid_uptimes) / len(valid_uptimes)
                if avg_container_uptime > 604800:
                    score_c = conf.POD_RUN_TIME_SCORE

            # GPU rarity weighting
            gpu_weight = sum(conf.GPU_MODEL_RATES.get(g.get("model"), 0) for g in r["gpu"])

            total_score = (score_a + score_b + score_c) * (1 + gpu_weight)
            scores.append(total_score)

        scores_result = np.array(scores)

        # Normalize scores so that sum = 1
        total_sum = np.sum(scores_result)
        if total_sum > 0:
            scores_result = scores_result / total_sum

        return scores_result