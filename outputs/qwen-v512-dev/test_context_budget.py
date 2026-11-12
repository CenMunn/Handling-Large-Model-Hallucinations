import unittest
from engine import safe_context_limit

class ContextBudgetTests(unittest.TestCase):
    def test_limit_follows_actual_slot_size(self):
        self.assertEqual(safe_context_limit({'default_generation_settings':{'n_ctx':12288}},12288),12288)
        self.assertEqual(safe_context_limit({'default_generation_settings':{'n_ctx':8192}},12288),8192)
        self.assertEqual(safe_context_limit({'default_generation_settings':{'n_ctx':32768}},12288),12288)
    def test_missing_or_invalid_props_falls_back_to_original_safe_limit(self):
        for data in ({}, {'default_generation_settings':{'n_ctx':0}}, {'default_generation_settings':{'n_ctx':'bad'}}):
            self.assertEqual(safe_context_limit(data,12288),8192)

if __name__=='__main__':unittest.main()
