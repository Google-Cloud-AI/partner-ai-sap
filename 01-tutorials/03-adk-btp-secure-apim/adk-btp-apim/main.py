# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
A sample script to optimize OpenAPI Spec file for OData APIs.
"""

import json
import re
import sys
import argparse

class ODataOpenAPIOptimizer:
    def __init__(self, spec_dict):
        self.spec = spec_dict
        self.paths = self.spec.get("paths", {})
        self.existing_ids = set()
        self.removed_endpoints = []

    def _auto_detect_child_entities(self):
        """
        Dynamically extracts child entity names from nested OData relationship paths
        (e.g., /_Item, /to_Partner) across OData v2 and OData v4 patterns.
        """
        child_entities = set()
        for path in self.paths.keys():
            # Match OData v4 style underscores, e.g., /_Item or /_Partner
            matches_v4 = re.findall(r'/_(Item|Partner|PricingElement|Text|ScheduleLine|Instance|Characteristic|AssignedValue|VariantConfiguration)', path)
            for m in matches_v4:
                child_entities.add(m.strip())
            
            # Match OData v2 style 'to_' prefixes, e.g., /to_Item
            matches_v2 = re.findall(r'/to_([^/()]+)', path)
            for m in matches_v2:
                child_entities.add(m.strip())
        return child_entities

    def _is_removable_flat_child_write(self, path, method, child_entities):
        """
        Detects flat child collections (e.g. POST /SalesOrderItem) that are missing
        parent keys in their request body schemas and should be pruned.
        """
        if method.lower() not in ['post', 'put', 'patch', 'delete']:
            return False
            
        is_root = False
        # Normalize and strip SAP table prefixes
        clean_path = path.lstrip('/').replace('A_', '').lower()
        if clean_path in ['salesorder', 'businesspartner', 'journalentry', 'customer']:
            is_root = True

        if is_root:
            return False

        # If it doesn't contain path parameters or navigation blocks, it is flat child write.
        if '{' not in path and '(' not in path and '/_' not in path and '/to_' not in path:
            for child in child_entities:
                if clean_path == child.lower() or clean_path == f"salesorder{child.lower()}" or clean_path == f"salesorderitem{child.lower()}":
                    return True
        return False

    def optimize(self):
        child_entities = self._auto_detect_child_entities()
        optimized_paths = {}

        for path, methods in self.paths.items():
            is_removable = False
            allowed_methods = {}

            for method, details in list(methods.items()):
                method_lower = method.lower()

                # Filter out broken flat write/delete endpoints
                if self._is_removable_flat_child_write(path, method, child_entities):
                    self.removed_endpoints.append(f"{method.upper()} {path}")
                    continue

                if method_lower not in ['get', 'post', 'put', 'patch', 'delete']:
                    allowed_methods[method] = details
                    continue

                # Detect key presence in the path (e.g. {SalesOrder} or ('{SalesOrder}'))
                is_single_resource = '{' in path or bool(re.search(r'\(\'.*?\'\)', path))

                clean_path = re.sub(r'\(.*?\)', '', path)
                segments = [s for s in clean_path.split('/') if s]

                processed_segments = []
                parent_resource = None
                for i, seg in enumerate(segments):
                    if seg.startswith('{') and seg.endswith('}'):
                        continue
                    if seg.startswith('to_'):
                        seg = seg[3:]
                    if seg.startswith('_'):
                        seg = seg[1:]
                    if seg.startswith('A_'):
                        seg = seg[2:]
                    processed_segments.append(seg)
                    if i == 0:
                        parent_resource = seg

                # Map HTTP methods to standard semantic verbs
                if method_lower == 'get':
                    verb = 'get' if is_single_resource else 'list'
                elif method_lower == 'post':
                    verb = 'create'
                elif method_lower in ['put', 'patch']:
                    verb = 'update'
                elif method_lower == 'delete':
                    verb = 'delete'
                else:
                    verb = method_lower

                # Construct semantic, clean operation ID
                if '/_' in path or '/to_' in path:
                    child_resource = processed_segments[-1]
                    op_id = f"{verb}{child_resource}For{parent_resource}"
                else:
                    op_id = f"{verb}{processed_segments[-1]}"

                # Clean non-alphanumeric chars and apply strict 64-char limit
                op_id = re.sub(r'[^a-zA-Z0-9_]', '', op_id)[:60]

                # Resolve naming collisions
                if op_id in self.existing_ids:
                    counter = 1
                    test_id = f"{op_id}_{counter}"
                    while test_id in self.existing_ids:
                        counter += 1
                        test_id = f"{op_id}_{counter}"
                    op_id = test_id

                self.existing_ids.add(op_id)
                details['operationId'] = op_id

                # Guide the agent regarding path parameter handling
                if is_single_resource:
                    desc = details.get('description', '')
                    if "WARNING:" not in desc:
                        details['description'] = desc.strip() + " WARNING: You must pass the required path parameter key(s) in the URL path."

                allowed_methods[method] = details

            if allowed_methods:
                optimized_paths[path] = allowed_methods

        self.spec['paths'] = optimized_paths
        return self.spec

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Optimize SAP OData specs for LLM Agent tool calling.")
    parser.add_argument("-i", "--input", required=True, help="Path to input raw OData JSON specification")
    parser.add_argument("-o", "--output", required=True, help="Path to save optimized output JSON specification")
    args = parser.parse_args()
    print(f"[*] Loading specification: {args.input}")
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            raw_spec = json.load(f)
    except Exception as e:
        print(f"[!] Error: Failed to load input file. {e}")
        sys.exit(1)
        
    optimizer = ODataOpenAPIOptimizer(raw_spec)
    optimized_spec = optimizer.optimize()
    
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(optimized_spec, f, indent=2)
        
    print(f"\n[+] Optimization Completed successfully!")
    print(f"    - Excluded {len(optimizer.removed_endpoints)} redundant direct collection write endpoints.")
    print(f"    - Injected {len(optimizer.existing_ids)} unique, collision-free, semantic operationId tags.")
    print(f"    - Optimized file successfully created: {args.output}\n")
