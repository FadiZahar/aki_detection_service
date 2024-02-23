# Creatine message!
# current [50 0 None None None None None]
# An error occurred: Expected 2D array, got 1D array instead:
# array=[ 50.        0.      127.56955       nan       nan       nan       nan
#        nan].
# Reshape your data either using array.reshape(-1, 1) if your data has a single feature or array.reshape(1, -1) if it contains a single sample.

#current_data = [36, 1, 140, 135, 129, None, None]
#current_data = [26, 0, 130, 135, None, None, None]
#current_data = [45, 1, 140, 135, 129, None, None]
#current_data = [61, 0, 140, 135, 129, 122, 123]

# Let's define the function to fill None values as described
def fill_none(data):
    # Copy the list to avoid modifying the original data
    filled_data = data.copy()
    # Find the rightmost non-None value starting from index 2
    for i in range(len(filled_data) - 1, 1, -1):
        if filled_data[i] is not None:
            rightmost_non_none = filled_data[i]
            break
    else:
        # If all values from index 2 onwards are None, use the value at index 2
        rightmost_non_none = filled_data[2]
    
    # Fill None values with the rightmost non-None value found
    for i in range(2, len(filled_data)):
        if filled_data[i] is None:
            filled_data[i] = rightmost_non_none
    
    return filled_data

# Example data
current_data_examples = [
    [36, 1, 140, 135, 129, None, None],
    [26, 0, 130, 135, None, None, None],
    [45, 1, 140, 135, 129, None, None],
    [61, 0, 140, 135, 129, 122, 123]
]

# Process each data example
filled_data_examples = [fill_none_with_last_non_none(data) for data in current_data_examples]
print(filled_data_examples)