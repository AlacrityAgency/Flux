"""Admission for actual rendered requests, independent of opaque CLI history/billing."""
from flux.knowledge.retrieval import token_count, digest


def admit_context(prompt, input_budget=16000, output_reserve=4000, window=24000):
    count=token_count(prompt)
    if count>input_budget or count+output_reserve>window or len(prompt)>59000:
        raise ValueError('Mandatory context exceeds the local input budget; split the task or narrow the evidence. No criterion/artifact was silently truncated.')
    return {'input_tokens_local':count,'input_budget':input_budget,'output_reserve_local':output_reserve,
            'window_assumption':window,'rendered_hash':digest(prompt),'provider_billing_measurement':False,
            'provider_hidden_context':'unknown','native_history':'fresh dedicated session'}
