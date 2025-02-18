from utils.file_parser import FileParser
import json

def main():
    parser = FileParser()
    
    # Test Python file parsing
    python_result = parser.parse_file("../data/sample_notebooks/example.py")
    print("\nPython File Parsing Result:")
    print(json.dumps(python_result, indent=2))
    
    # Test Notebook parsing
    notebook_result = parser.parse_file("../data/sample_notebooks/example.ipynb")
    print("\nJupyter Notebook Parsing Result:")
    print(json.dumps(notebook_result, indent=2))

if __name__ == "__main__":
    main()
