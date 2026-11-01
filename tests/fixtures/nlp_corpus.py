"""Comprehensive Human-Authored NLP Evaluation Corpus for RE-PLAN-V.

Contains >= 20 diverse natural language prompts per domain across all 6 registered
domains, plus ambiguous prompts requiring clarification, unsupported domain prompts,
and invalid / contradictory prompts (145 prompts total).
"""

from __future__ import annotations
from typing import Dict, List, NamedTuple, Optional
from interpretation.router import RoutingOutcome


class NLPCorpusCase(NamedTuple):
    prompt_id: str
    prompt: str
    expected_outcome: RoutingOutcome
    expected_domain: Optional[str] = None
    expected_negative_pred: Optional[str] = None
    expected_entities: Optional[List[str]] = None


# Blocks World Corpus: 20 prompts
BLOCKS_WORLD_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("BW-01", "Stack the red box on the blue box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["red_box", "blue_box"]),
    NLPCorpusCase("BW-02", "Move the green box on the red box. Do not move the glass.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["green_box", "red_box", "glass"]),
    NLPCorpusCase("BW-03", "Put yellow_box on green_box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["yellow_box", "green_box"]),
    NLPCorpusCase("BW-04", "Place block_1 on block_2. Do not touch block_3.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["block_1", "block_2", "block_3"]),
    NLPCorpusCase("BW-05", "Stack b1 on b2, then stack b3 on b1.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["b1", "b2", "b3"]),
    NLPCorpusCase("BW-06", "Put the blue box on the table.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["blue_box"]),
    NLPCorpusCase("BW-07", "Stack the red box on the yellow box without placing green_box on blue_box.", RoutingOutcome.SUPPORTED, "blocks_world", "on", ["red_box", "yellow_box", "green_box", "blue_box"]),
    NLPCorpusCase("BW-08", "Move box_a next to box_b.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["box_a", "box_b"]),
    NLPCorpusCase("BW-09", "Pick up b1 and stack it on b2.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["b1", "b2"]),
    NLPCorpusCase("BW-10", "Put the glass on the table. Do not move the red box.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["glass", "red_box"]),
    NLPCorpusCase("BW-11", "Stack the blue box on top of the green box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["blue_box", "green_box"]),
    NLPCorpusCase("BW-12", "Move the orange box on the purple box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["orange_box", "purple_box"]),
    NLPCorpusCase("BW-13", "Unstack the red box and place it on the table.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["red_box"]),
    NLPCorpusCase("BW-14", "Stack red_box on blue_box. Avoid yellow_box.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["red_box", "blue_box", "yellow_box"]),
    NLPCorpusCase("BW-15", "Construct a tower: stack yellow_box on green_box and green_box on blue_box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["yellow_box", "green_box", "blue_box"]),
    NLPCorpusCase("BW-16", "Place b2 on b1. Never touch b4.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["b2", "b1", "b4"]),
    NLPCorpusCase("BW-17", "Put the white box on the black box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["white_box", "black_box"]),
    NLPCorpusCase("BW-18", "Move block_x on block_y. Without moving block_z.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["block_x", "block_y", "block_z"]),
    NLPCorpusCase("BW-19", "Stack the black box on the red box. Do not touch the glass.", RoutingOutcome.SUPPORTED, "blocks_world", "holding", ["black_box", "red_box", "glass"]),
    NLPCorpusCase("BW-20", "Move the blue box on the table and stack the green box on the red box.", RoutingOutcome.SUPPORTED, "blocks_world", expected_entities=["blue_box", "green_box", "red_box"]),
]

# Grid World Corpus: 20 prompts
GRID_WORLD_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("GW-01", "Move the agent from cell_a to cell_b.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "cell_a", "cell_b"]),
    NLPCorpusCase("GW-02", "Navigate the agent from loc_0_0 to loc_1_1.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "loc_0_0", "loc_1_1"]),
    NLPCorpusCase("GW-03", "Move agent from loc_0_0 to loc_2_2. Do not enter loc_1_1.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "loc_0_0", "loc_2_2", "cell_loc_1_1"]),
    NLPCorpusCase("GW-04", "Move from cell_1 to cell_2 and pick up key_1.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "cell_1", "cell_2", "key_1"]),
    NLPCorpusCase("GW-05", "Navigate agent from pos_0_0 to pos_0_2.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent"]),
    NLPCorpusCase("GW-06", "Move the agent from cell_start to cell_goal. Avoid cell_obstacle.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "cell_start", "cell_goal", "cell_obstacle"]),
    NLPCorpusCase("GW-07", "Move agent from loc_1_0 to loc_1_2. Do not visit loc_1_1.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "loc_1_0", "loc_1_2"]),
    NLPCorpusCase("GW-08", "Traverse the grid from cell_a to cell_c without entering cell_b.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "cell_a", "cell_c", "cell_b"]),
    NLPCorpusCase("GW-09", "Move agent from loc_0_0 to loc_3_3. Never enter loc_2_2.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "loc_0_0", "loc_3_3"]),
    NLPCorpusCase("GW-10", "Navigate to cell_exit from cell_entry and collect item_gold.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "cell_exit", "cell_entry", "item_gold"]),
    NLPCorpusCase("GW-11", "Move the agent from loc_a to loc_b.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "loc_a", "loc_b"]),
    NLPCorpusCase("GW-12", "Go from cell_north to cell_south. Do not visit cell_center.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "cell_north", "cell_south", "cell_center"]),
    NLPCorpusCase("GW-13", "Navigate from loc_0_1 to loc_2_1.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "loc_0_1", "loc_2_1"]),
    NLPCorpusCase("GW-14", "Move agent from cell_x to cell_y. Avoid cell_hazard.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "cell_x", "cell_y", "cell_hazard"]),
    NLPCorpusCase("GW-15", "Pick up token_1 at cell_b and navigate agent from cell_a to cell_b.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "token_1", "cell_a", "cell_b"]),
    NLPCorpusCase("GW-16", "Travel from loc_1_1 to loc_3_1 without traversing cell_blocked.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "loc_1_1", "loc_3_1", "cell_blocked"]),
    NLPCorpusCase("GW-17", "Move from cell_origin to cell_target. Do not touch item_trap.", RoutingOutcome.SUPPORTED, "grid_world", "holding_item", ["agent", "cell_origin", "cell_target", "item_trap"]),
    NLPCorpusCase("GW-18", "Navigate the agent across the grid from loc_0_0 to loc_2_0.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "loc_0_0", "loc_2_0"]),
    NLPCorpusCase("GW-19", "Go to loc_finish from loc_start. Never visit loc_pit.", RoutingOutcome.SUPPORTED, "grid_world", "at", ["agent", "loc_finish", "loc_start"]),
    NLPCorpusCase("GW-20", "Move agent from cell_alpha to cell_beta and pick up key_2.", RoutingOutcome.SUPPORTED, "grid_world", expected_entities=["agent", "cell_alpha", "cell_beta", "key_2"]),
]

# Household Robotics Corpus: 20 prompts
HOUSEHOLD_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("HH-01", "Move the mug from the kitchen shelf to the living room table.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "mug", "kitchen", "living_room"]),
    NLPCorpusCase("HH-02", "Pick up the cup from the kitchen counter and place it on the dining_room table.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "cup", "kitchen", "dining_room"]),
    NLPCorpusCase("HH-03", "Move the plate from the kitchen to the living_room table. Do not enter the bedroom.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "plate", "kitchen", "bedroom"]),
    NLPCorpusCase("HH-04", "Fetch the book from the office desk and place it on the living_room table.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "book", "office", "living_room"]),
    NLPCorpusCase("HH-05", "Move the bowl from the kitchen counter to the pantry shelf. Avoid the office.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "bowl", "kitchen", "office"]),
    NLPCorpusCase("HH-06", "Take the bottle from the kitchen table and put it on the bedroom nightstand.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "bottle", "kitchen", "bedroom"]),
    NLPCorpusCase("HH-07", "Move the sponge from the kitchen to the bathroom counter.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "sponge", "kitchen", "bathroom"]),
    NLPCorpusCase("HH-08", "Transport the apple from the dining_room table to the kitchen counter. Do not touch the vase.", RoutingOutcome.SUPPORTED, "household_robotics", "holding", ["robot", "apple", "vase"]),
    NLPCorpusCase("HH-09", "Move the dish from the dining_room to the kitchen counter.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "dish", "dining_room", "kitchen"]),
    NLPCorpusCase("HH-10", "Fetch the remote from the living_room table and place it on the bedroom desk.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "living_room", "bedroom"]),
    NLPCorpusCase("HH-11", "Move the water bottle from the office desk to the kitchen counter. Avoid the bedroom.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "bottle", "office", "bedroom"]),
    NLPCorpusCase("HH-12", "Carry the clean cup from the kitchen shelf to the office desk.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "cup", "kitchen", "office"]),
    NLPCorpusCase("HH-13", "Move item_keys from the hallway table to the living_room shelf.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "item_keys", "hallway", "living_room"]),
    NLPCorpusCase("HH-14", "Transport the vase from the living_room table to the dining_room counter. Do not touch the glass.", RoutingOutcome.SUPPORTED, "household_robotics", "holding", ["robot", "vase", "glass"]),
    NLPCorpusCase("HH-15", "Move the plate from the kitchen counter to the dining_room table without entering the hallway.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "plate", "kitchen", "hallway"]),
    NLPCorpusCase("HH-16", "Tidy up: move the book from the bedroom nightstand to the living_room shelf.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "book", "bedroom", "living_room"]),
    NLPCorpusCase("HH-17", "Move the bowl from the dining_room table to the kitchen counter. Avoid the bathroom.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "bowl", "bathroom"]),
    NLPCorpusCase("HH-18", "Carry the mug from the office desk to the kitchen shelf. Never enter the bedroom.", RoutingOutcome.SUPPORTED, "household_robotics", "robot_at", ["robot", "mug", "bedroom"]),
    NLPCorpusCase("HH-19", "Fetch the bottle from the bathroom shelf and place it on the bedroom table.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "bottle", "bathroom", "bedroom"]),
    NLPCorpusCase("HH-20", "Move the plate from the kitchen counter to the living_room table.", RoutingOutcome.SUPPORTED, "household_robotics", expected_entities=["robot", "plate", "kitchen", "living_room"]),
]

# Warehouse Corpus: 20 prompts
WAREHOUSE_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("WH-01", "Move SKU_A from shelf_1 to dispatch dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "sku_a", "shelf_1", "dispatch_dock"]),
    NLPCorpusCase("WH-02", "Retrieve sku_101 from shelf_1 and deposit into dispatch_dock. Do not enter zone_b.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_101", "shelf_1", "zone_b"]),
    NLPCorpusCase("WH-03", "Transfer package_b from bay_1 to dispatch_dock using carrier_1.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "package_b", "bay_1", "dispatch_dock"]),
    NLPCorpusCase("WH-04", "Move widget_1 from shelf_storage to receiving_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "widget_1", "receiving_dock"]),
    NLPCorpusCase("WH-05", "Retrieve sku_42 from shelf_2 and deposit to dispatch_dock. Avoid zone_hazard.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_42", "zone_hazard"]),
    NLPCorpusCase("WH-06", "AGV transit: move part_99 from bay_alpha to bay_beta.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "part_99", "bay_alpha", "bay_beta"]),
    NLPCorpusCase("WH-07", "Retrieve sku_electronics from shelf_3 and store in dispatch_dock. Do not visit zone_cold_storage.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_electronics", "zone_cold_storage"]),
    NLPCorpusCase("WH-08", "Move box_10 from shelf_1 to dispatch_dock using agv_2.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["agv_2", "box_10", "shelf_1", "dispatch_dock"]),
    NLPCorpusCase("WH-09", "Transfer sku_heavy from shelf_1 to dispatch_dock without traversing zone_restricted.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_heavy", "zone_restricted"]),
    NLPCorpusCase("WH-10", "Move pallet_a from shelf_1 to dispatch_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "pallet_a"]),
    NLPCorpusCase("WH-11", "Retrieve sku_medical from shelf_4 and deposit to dispatch_dock. Avoid zone_quarantine.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_medical", "zone_quarantine"]),
    NLPCorpusCase("WH-12", "Carrier_1 transport package_alpha from shelf_10 to dispatch_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "package_alpha", "shelf_10", "dispatch_dock"]),
    NLPCorpusCase("WH-13", "Move sku_fragile from bay_5 to dispatch_dock. Do not retrieve sku_damaged.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_loaded_with", ["carrier_1", "sku_fragile", "sku_damaged"]),
    NLPCorpusCase("WH-14", "Retrieve item_c from shelf_1 and place into dispatch_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "shelf_1", "dispatch_dock"]),
    NLPCorpusCase("WH-15", "Transit carrier from zone_storage to zone_dock and deliver sku_x to dispatch_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "sku_x", "dispatch_dock"]),
    NLPCorpusCase("WH-16", "Move sku_77 from shelf_2 to dispatch_dock. Never enter zone_maintenance.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_77", "zone_maintenance"]),
    NLPCorpusCase("WH-17", "Transfer widget_b from bay_3 to receiving_dock using carrier_2.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_2", "widget_b", "bay_3", "receiving_dock"]),
    NLPCorpusCase("WH-18", "Move part_metal from shelf_1 to dispatch_dock. Do not enter zone_chemicals.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "part_metal", "zone_chemicals"]),
    NLPCorpusCase("WH-19", "AGV move package_55 from bay_1 to dispatch_dock.", RoutingOutcome.SUPPORTED, "warehouse", expected_entities=["carrier_1", "package_55", "dispatch_dock"]),
    NLPCorpusCase("WH-20", "Retrieve sku_component from shelf_6 and deposit into dispatch_dock without entering zone_congested.", RoutingOutcome.SUPPORTED, "warehouse", "carrier_at", ["carrier_1", "sku_component", "zone_congested"]),
]

# Scheduling Corpus: 20 prompts
SCHEDULING_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("SC-01", "Schedule design_review before code_review on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["design_review", "code_review", "machine_1"]),
    NLPCorpusCase("SC-02", "Allocate job_alpha before job_beta on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["job_alpha", "job_beta", "machine_1"]),
    NLPCorpusCase("SC-03", "Schedule job_1 before job_2 on machine_1. Do not schedule job_3 on machine_2.", RoutingOutcome.SUPPORTED, "scheduling", "job_assigned", ["job_1", "job_2", "job_3", "machine_2"]),
    NLPCorpusCase("SC-04", "Plan the precedence: data_sync before backup_job on server_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["data_sync", "backup_job", "server_1"]),
    NLPCorpusCase("SC-05", "Schedule task_a before task_b on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_a", "task_b", "machine_1"]),
    NLPCorpusCase("SC-06", "Allocate task_frontend before task_backend on machine_2.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_frontend", "task_backend", "machine_2"]),
    NLPCorpusCase("SC-07", "Schedule qa_testing before deploy_job on server_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["qa_testing", "deploy_job", "server_1"]),
    NLPCorpusCase("SC-08", "Schedule audit_job before review_job on machine_3.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["audit_job", "review_job", "machine_3"]),
    NLPCorpusCase("SC-09", "Allocate compute task_prep before task_eval on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_prep", "task_eval", "machine_1"]),
    NLPCorpusCase("SC-10", "Schedule sync_task before report_task on server_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["sync_task", "report_task", "server_1"]),
    NLPCorpusCase("SC-11", "Assign task_data_prep before task_model_fit on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_data_prep", "task_model_fit", "machine_1"]),
    NLPCorpusCase("SC-12", "Schedule build_job before test_job on worker_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["build_job", "test_job", "worker_1"]),
    NLPCorpusCase("SC-13", "Allocate job_ingest before job_transform on cpu_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["job_ingest", "job_transform", "cpu_1"]),
    NLPCorpusCase("SC-14", "Schedule job_alpha and job_beta on machine_1 with precedence job_alpha before job_beta.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["job_alpha", "job_beta", "machine_1"]),
    NLPCorpusCase("SC-15", "Schedule backup_job before sync_task on server_2. Do not schedule backup_job on server_old.", RoutingOutcome.SUPPORTED, "scheduling", "job_assigned", ["backup_job", "server_2", "server_old"]),
    NLPCorpusCase("SC-16", "Plan workflow: task_compile before task_package on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_compile", "task_package", "machine_1"]),
    NLPCorpusCase("SC-17", "Schedule review_arch before review_security on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["review_arch", "review_security", "machine_1"]),
    NLPCorpusCase("SC-18", "Allocate task_render_1 before task_render_2 on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["task_render_1", "task_render_2", "machine_1"]),
    NLPCorpusCase("SC-19", "Schedule job_checkout before job_verify on server_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["job_checkout", "job_verify", "server_1"]),
    NLPCorpusCase("SC-20", "Assign data_sync before backup_job on machine_1.", RoutingOutcome.SUPPORTED, "scheduling", expected_entities=["data_sync", "backup_job", "machine_1"]),
]

# Software Workflow Corpus: 20 prompts
SOFTWARE_WORKFLOW_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("SW-01", "Build and test commit_v1, then deploy to staging environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v1", "staging"]),
    NLPCorpusCase("SW-02", "Run security scan and deploy commit_v2 to production. Do not deploy to staging.", RoutingOutcome.SUPPORTED, "software_workflow", "deployed_to", ["commit_v2", "production", "staging"]),
    NLPCorpusCase("SW-03", "Deploy pkg_release_v1 to staging environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["staging"]),
    NLPCorpusCase("SW-04", "Build artifact for commit_abc, run unit tests, and deploy to qa.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_abc", "qa"]),
    NLPCorpusCase("SW-05", "Execute unit tests on commit_100 and deploy pkg_100 to production.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_100", "production"]),
    NLPCorpusCase("SW-06", "Run security scan on commit_main and deploy to staging.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_main", "staging"]),
    NLPCorpusCase("SW-07", "Build and deploy release_v3 to canary environment. Do not deploy to production.", RoutingOutcome.SUPPORTED, "software_workflow", "deployed_to", ["release_v3", "canary", "production"]),
    NLPCorpusCase("SW-08", "Test commit_v4, build pkg_v4, and deploy to testing environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v4", "testing"]),
    NLPCorpusCase("SW-09", "Deploy pkg_auth to staging after running security scan.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["staging"]),
    NLPCorpusCase("SW-10", "Compile commit_login and deploy to dev environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_login", "dev"]),
    NLPCorpusCase("SW-11", "Run unit tests on commit_v5, grant approval, and deploy to production.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v5", "production"]),
    NLPCorpusCase("SW-12", "Build pkg_backend for commit_v6 and deploy to staging environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v6", "staging"]),
    NLPCorpusCase("SW-13", "Run security scan on commit_fix_ssl and deploy to production without deploying to canary.", RoutingOutcome.SUPPORTED, "software_workflow", "deployed_to", ["commit_fix_ssl", "production", "canary"]),
    NLPCorpusCase("SW-14", "Test and scan commit_77, then deploy pkg_77 to staging.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_77", "staging"]),
    NLPCorpusCase("SW-15", "Deploy release_v2 to production environment. Avoid staging.", RoutingOutcome.SUPPORTED, "software_workflow", "deployed_to", ["release_v2", "production", "staging"]),
    NLPCorpusCase("SW-16", "Build container image for commit_v8 and deploy to qa environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v8", "qa"]),
    NLPCorpusCase("SW-17", "Deploy pkg_frontend to dev environment after test verification.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["dev"]),
    NLPCorpusCase("SW-18", "Execute unit tests on commit_v9 and deploy to staging environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_v9", "staging"]),
    NLPCorpusCase("SW-19", "Run security audit on commit_release and deploy to production.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_release", "production"]),
    NLPCorpusCase("SW-20", "Build artifact from commit_stable and deploy to staging environment.", RoutingOutcome.SUPPORTED, "software_workflow", expected_entities=["commit_stable", "staging"]),
]

# Ambiguity / Clarification Required: 10 prompts
CLARIFICATION_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("CL-01", "Deliver the package.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-02", "Move.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-03", "Schedule.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-04", "Deploy.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-05", "Deliver the box to destination.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-06", "Transport.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-07", "Schedule task.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-08", "Deploy software.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-09", "Ship the package.", RoutingOutcome.NEEDS_CLARIFICATION),
    NLPCorpusCase("CL-10", "Allocate resource.", RoutingOutcome.NEEDS_CLARIFICATION),
]

# Unsupported Domain Rejections: 10 prompts
UNSUPPORTED_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("UN-01", "Book a flight ticket from Paris to New York and reserve a hotel room.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-02", "What is the stock price of Apple today and should I buy crypto?", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-03", "Predict the weather forecast in Tokyo for tomorrow.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-04", "Diagnose my symptoms: headache, sore throat, and mild fever, prescribe medicine.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-05", "Translate this paragraph to French: the quick brown fox jumps over the lazy dog.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-06", "Generate a romantic poem about autumn leaves.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-07", "Write a fictional fantasy story about elves and dragons in a castle.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-08", "Tell me a funny joke about software engineers.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-09", "Give me a recipe for chocolate chip cookies and how to bake a cake.", RoutingOutcome.UNSUPPORTED),
    NLPCorpusCase("UN-10", "Simulate a quantum superposition gate using Shor's algorithm.", RoutingOutcome.UNSUPPORTED),
]

# Invalid / Boundary Prompts: 5 prompts
INVALID_CORPUS: List[NLPCorpusCase] = [
    NLPCorpusCase("INV-01", "", RoutingOutcome.INVALID_PROPOSAL),
    NLPCorpusCase("INV-02", "   \n\t  ", RoutingOutcome.INVALID_PROPOSAL),
    NLPCorpusCase("INV-03", "12345 67890 !@#$%^&*()", RoutingOutcome.INVALID_PROPOSAL),
    NLPCorpusCase("INV-04", "a " * 1500, RoutingOutcome.INVALID_PROPOSAL),
    NLPCorpusCase("INV-05", "??? ... !!!", RoutingOutcome.INVALID_PROPOSAL),
]
