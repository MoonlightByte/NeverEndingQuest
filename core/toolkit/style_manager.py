#!/usr/bin/env python3
"""
Style Template Manager for Module Toolkit
Handles style prompts and custom template creation
"""

import json
from pathlib import Path
from typing import Dict, Optional, List

class StyleManager:
    """Manages style templates for monster generation"""
    
    TEMPLATES_FILE = "data/style_templates.json"
    
    def __init__(self):
        """Initialize the style manager"""
        self.templates_path = Path(self.TEMPLATES_FILE)
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Load style templates from file"""
        if self.templates_path.exists():
            with open(self.templates_path, 'r') as f:
                return json.load(f)
        else:
            # Create default templates if file doesn't exist
            default = {
                "builtin": {
                    "photorealistic": {
                        "name": "Photorealistic",
                        "prompt": "ultra-realistic, professional photography, detailed textures, natural lighting"
                    }
                },
                "custom": {}
            }
            self._save_templates(default)
            return default
    
    def _save_templates(self, templates: Dict = None):
        """Save templates to file"""
        if templates is None:
            templates = self.templates
        
        self.templates_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.templates_path, 'w') as f:
            json.dump(templates, f, indent=2)
    
    def get_style_prompt(self, style_id: str) -> Optional[str]:
        """
        Get the prompt for a specific style
        
        Args:
            style_id: The style identifier
            
        Returns:
            The style prompt or None if not found
        """
        # Check builtin styles first
        if style_id in self.templates.get("builtin", {}):
            return self.templates["builtin"][style_id]["prompt"]
        
        # Check custom styles
        if style_id in self.templates.get("custom", {}):
            return self.templates["custom"][style_id]["prompt"]
        
        return None
    
    def get_all_styles(self) -> Dict:
        """
        Get all available styles
        
        Returns:
            Dictionary of all styles with their metadata
        """
        all_styles = {}
        
        # Add builtin styles
        for style_id, style_data in self.templates.get("builtin", {}).items():
            all_styles[style_id] = {
                "name": style_data["name"],
                "prompt": style_data["prompt"],
                "type": "builtin"
            }
        
        # Add custom styles
        for style_id, style_data in self.templates.get("custom", {}).items():
            all_styles[style_id] = {
                "name": style_data["name"],
                "prompt": style_data["prompt"],
                "type": "custom"
            }
        
        return all_styles
    
    def save_custom_style(self, name: str, prompt: str, style_id: str = None) -> Dict:
        """
        Save a new custom style template

        Args:
            name: Display name for the style
            prompt: The prompt appendage for this style
            style_id: Optional existing style_id to update instead of creating new

        Returns:
            Result dictionary with success status
        """
        # If updating existing style, use provided style_id
        if style_id:
            # Don't allow overriding builtins through this method
            if style_id in self.templates.get("builtin", {}):
                return {
                    "success": False,
                    "error": f"Cannot override builtin style. Use overwrite_style() instead."
                }

            # Update existing custom style
            if "custom" not in self.templates:
                self.templates["custom"] = {}

            self.templates["custom"][style_id] = {
                "name": name,
                "prompt": prompt
            }

            self._save_templates()

            return {
                "success": True,
                "style_id": style_id,
                "message": f"Custom style '{name}' updated successfully"
            }

        # Otherwise create new style with ID from name
        new_style_id = name.lower().replace(" ", "_")

        # Check if already exists
        if new_style_id in self.templates.get("builtin", {}):
            return {
                "success": False,
                "error": f"Cannot override builtin style '{name}'"
            }

        if new_style_id in self.templates.get("custom", {}):
            return {
                "success": False,
                "error": f"Custom style '{name}' already exists. Use a different name or update the existing one."
            }

        # Add to custom styles
        if "custom" not in self.templates:
            self.templates["custom"] = {}

        self.templates["custom"][new_style_id] = {
            "name": name,
            "prompt": prompt
        }

        # Save to file
        self._save_templates()

        return {
            "success": True,
            "style_id": new_style_id,
            "message": f"Custom style '{name}' saved successfully"
        }
    
    def delete_custom_style(self, style_id: str) -> Dict:
        """
        Delete a custom style template
        
        Args:
            style_id: The style identifier to delete
            
        Returns:
            Result dictionary with success status
        """
        # Cannot delete builtin styles
        if style_id in self.templates.get("builtin", {}):
            return {
                "success": False,
                "error": "Cannot delete builtin styles"
            }
        
        # Check if exists in custom
        if style_id not in self.templates.get("custom", {}):
            return {
                "success": False,
                "error": f"Custom style '{style_id}' not found"
            }
        
        # Delete the style
        style_name = self.templates["custom"][style_id]["name"]
        del self.templates["custom"][style_id]
        
        # Save to file
        self._save_templates()
        
        return {
            "success": True,
            "message": f"Custom style '{style_name}' deleted"
        }
    
    def update_custom_style(self, style_id: str, prompt: str) -> Dict:
        """
        Update an existing custom style's prompt
        
        Args:
            style_id: The style identifier
            prompt: New prompt text
            
        Returns:
            Result dictionary with success status
        """
        # Cannot update builtin styles
        if style_id in self.templates.get("builtin", {}):
            return {
                "success": False,
                "error": "Cannot modify builtin styles"
            }
        
        # Check if exists in custom
        if style_id not in self.templates.get("custom", {}):
            return {
                "success": False,
                "error": f"Custom style '{style_id}' not found"
            }
        
        # Update the prompt
        self.templates["custom"][style_id]["prompt"] = prompt
        
        # Save to file
        self._save_templates()
        
        return {
            "success": True,
            "message": f"Style '{style_id}' updated"
        }
    
    def overwrite_style(self, style_id: str, prompt: str) -> Dict:
        """
        Overwrite any style (builtin or custom) by saving as custom
        
        Args:
            style_id: The style identifier to overwrite
            prompt: New prompt text
            
        Returns:
            Result dictionary with success status
        """
        # If it's a builtin style, save as custom with same ID
        if style_id in self.templates.get("builtin", {}):
            # Get the original style name
            original = self.templates["builtin"][style_id]
            
            # Save as custom style with same ID
            if "custom" not in self.templates:
                self.templates["custom"] = {}
            
            self.templates["custom"][style_id] = {
                "name": original["name"] + " (Modified)",
                "prompt": prompt
            }
            
            self._save_templates()
            
            return {
                "success": True,
                "message": f"Builtin style '{style_id}' overwritten as custom"
            }
        
        # If it's already custom, just update it
        elif style_id in self.templates.get("custom", {}):
            self.templates["custom"][style_id]["prompt"] = prompt
            self._save_templates()
            
            return {
                "success": True,
                "message": f"Custom style '{style_id}' updated"
            }
        
        # If it doesn't exist, create new custom
        else:
            if "custom" not in self.templates:
                self.templates["custom"] = {}
            
            self.templates["custom"][style_id] = {
                "name": style_id.replace("_", " ").title(),
                "prompt": prompt
            }
            
            self._save_templates()
            
            return {
                "success": True,
                "message": f"New custom style '{style_id}' created"
            }


# CLI interface for testing
def main():
    """Command-line interface for style management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage style templates")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # List styles
    list_parser = subparsers.add_parser('list', help='List all styles')
    
    # Get style prompt
    get_parser = subparsers.add_parser('get', help='Get style prompt')
    get_parser.add_argument('style', help='Style ID')
    
    # Add custom style
    add_parser = subparsers.add_parser('add', help='Add custom style')
    add_parser.add_argument('name', help='Style name')
    add_parser.add_argument('prompt', help='Style prompt')
    
    # Delete custom style
    delete_parser = subparsers.add_parser('delete', help='Delete custom style')
    delete_parser.add_argument('style', help='Style ID')
    
    args = parser.parse_args()
    
    manager = StyleManager()
    
    if args.command == 'list':
        styles = manager.get_all_styles()
        print("\nAvailable Style Templates:")
        print("-" * 60)
        for style_id, data in styles.items():
            print(f"\n{style_id} ({data['type']})")
            print(f"  Name: {data['name']}")
            print(f"  Prompt: {data['prompt'][:80]}...")
    
    elif args.command == 'get':
        prompt = manager.get_style_prompt(args.style)
        if prompt:
            print(f"Prompt for '{args.style}':")
            print(prompt)
        else:
            print(f"Style '{args.style}' not found")
    
    elif args.command == 'add':
        result = manager.save_custom_style(args.name, args.prompt)
        if result['success']:
            print(result['message'])
        else:
            print(f"Failed: {result['error']}")
    
    elif args.command == 'delete':
        result = manager.delete_custom_style(args.style)
        if result['success']:
            print(result['message'])
        else:
            print(f"Failed: {result['error']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()