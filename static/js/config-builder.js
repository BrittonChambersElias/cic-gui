$(document).ready(function() {
    let currentFilters = {};
    let selectedRows = new Set();  
    var pendingUpdates = []; 

    function initializeDataTables() {
        var table = $('#myTable').DataTable({
            columnDefs: [
                { targets: 0, visible: false }, // Hides the UID column
                {
                    targets: -1, // Points to the last column where the 'Select' button is
                    orderable: false,
                    searchable: false,
                    width: "100px"
                }
            ],
            order: [] 
        });
    
        // Event binding for selectRow buttons in table body
        $('#myTable tbody').on('click', 'button.selectRowButton', function(e) {
            e.stopPropagation(); // Stops the event from bubbling up to other event handlers
            toggleRowSelection($(this).closest('tr'));
        });
    
        // Add ID or click event directly to the header cell after DataTable initialization
        $('#myTable thead th:last-child').click(function() {
            let allSelected = true;
            $('#myTable tbody tr').each(function() {
                if (!$(this).hasClass('selected')) {
                    allSelected = false;
                }
            });
    
            $('#myTable tbody tr').each(function() {
                if (allSelected) {
                    deselectRow($(this));
                } else {
                    selectRow($(this));
                }
            });
        });
    
        function toggleRowSelection(tr) {
            var uid = tr.attr('data-uid');  // Assuming each row has a 'data-uid' attribute
            if (tr.hasClass('selected')) {
                deselectRow(tr);
            } else {
                selectRow(tr);
            }
        }
    
        function selectRow(tr) {
            var uid = tr.attr('data-uid');
            selectedRows.add(uid);
            tr.addClass('selected');
        }
    
        function deselectRow(tr) {
            var uid = tr.attr('data-uid');
            selectedRows.delete(uid);
            tr.removeClass('selected');
        }
    }

    
    function updateFilterOptions(filterOptions, filterValues) {
        var filterHtml = '';
        filterOptions.forEach(function(option) {
            console.log("Processing option:", option);
            if (option === 'All') return;
            filterHtml += `<div class="col-md-3"><div class="form-group"><label for="filter${option}">${option}:</label>`;
            filterHtml += `<select id="filter${option}" class="form-control select2" multiple>`;
            
            // Check if filterValues for this option exists before trying to iterate
            if (filterValues[option]) {
                filterValues[option].forEach(function(value) {
                    let isSelected = currentFilters[option] && currentFilters[option].includes(value) ? 'selected' : '';
                    filterHtml += `<option value="${value}" ${isSelected}>${value}</option>`;
                });
            } else {
                console.warn(`No filter values available for ${option}`);
            }
    
            filterHtml += '</select></div></div>';
        });
    
        $('#filterOptions').html('<div class="row">' + filterHtml + '</div>');
        

        $('.select2').select2({
            width: '100%',
            placeholder: "Select an option",
            allowClear: true, // This adds the "All" functionality
            closeOnSelect: false // Keeps the dropdown open for multiple selections
        });
    }
    
    // AJAX call to fetch and display filtered data based on selected filters
    function fetchAndDisplayData() {
        // Update currentFilters based on the current state of Select2 dropdowns
        $('.select2').each(function() {
            let filterName = this.id.replace('filter', '');
            let selectedValues = $(this).val();
            
            if (selectedValues && selectedValues.length > 0) {
                // Only add to currentFilters if one or more selections are made
                currentFilters[filterName] = selectedValues;
            } else {
                // Ensure any previous filter for this category is cleared if no selection is made
                delete currentFilters[filterName];
            }
        });
        console.log("Current filters being sent:", currentFilters);
        $.ajax({
            url: '/display',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                'data_type': $('#data_type').val(),
                'filters': currentFilters
            }),
            success: function(response) {
                console.log("Received response:", response);
                // Check if response contains 'isValid' property
                if (typeof response.isValid !== 'undefined') {
                    if (response.isValid) {
                        $('#tableContainer').html(response.html);
                        initializeDataTables(); // Re-initialize DataTables for the new table
                    } else {
                        // Display feedback to the user if not valid
                        alert(response.errorMessage || "An error occurred."); // Fallback error message
                    }
                } else {
                    // If 'isValid' is not in the response, proceed as usual
                    $('#tableContainer').html(response.html);
                    initializeDataTables();
                }
                // Always update filter options and reinitialize select2
                updateFilterOptions(response.filterOptions, response.filterValues);
            },
            error: function(xhr, status, error) {
                console.error("Error: " + status + " " + error);
            }
        });
    }

    // Function to show/hide buttons based on the selected Data Type
    function toggleButtons() {
        var dataType = $("#data_type").val();
        if (dataType === 'Thresholds') {
            $("#addThresholdRowButton").show();
            $("#addFailureReasonRowButton").hide();
        } else if (dataType === 'Failure Reasons') {
            $("#addThresholdRowButton").hide();
            $("#addFailureReasonRowButton").show();
        }
    }

    // Function to get the UID of the selected row for add row above or below
    function getSelectedRowUid() {
        var selectedRow = $('#myTable tbody tr.selected');
        if (selectedRow.length > 0) {
            console.log("Selected Row UID: ", selectedRow.attr('data-uid'));
            return selectedRow.attr('data-uid');
        } else {
            alert("Please select a row to add a new row above or below.");
            return null;
        }
        
    }
    // Function to get the UID of the selected row for the delete button option
    function getSelectedRowUids() {
        var uids = [];
        $('#myTable tbody tr.selected').each(function() {
            uids.push($(this).attr('data-uid'));
        });
        return uids;
    }
    
    function batchUpdateData() {
        if (pendingUpdates.length > 0) {
            $.ajax({
                url: '/batch_update_cells',
                type: 'POST',
                contentType: 'application/json',
                data: JSON.stringify(pendingUpdates),
                success: function(response) {
                    console.log("Batch update successful:", response);
                    pendingUpdates = []; // Clear pending updates after successful batch update
                    //fetchAndDisplayData();  // Optionally refresh the table to reflect changes
                },
                error: function(xhr, status, error) {
                    console.error("Error during batch update: ", status, error);
                    alert("Error updating rows. Please try again.");
                }
            });
        }
    }
    

    function sendRowData(newData) {
        $.ajax({
            url: '/add_individual_row',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(newData),
            success: function(response) {
                if (response.status === 'success') {
                    alert("Row added successfully!");
                    fetchAndDisplayData(); // Refresh the table display
                    // Update the UI to reflect the newly added row
                    // Highlight the new row if necessary
                    let newUid = response.newUid;
                    highlightNewRow(newUid);  // Implement this function based on your UI requirements
                } else {
                    alert("Error adding row: " + response.message);
                }
            },
            error: function(xhr, status, error) {
                console.error("Error adding row: ", status, error);
                alert("Error adding row: " + error);
            }
        });
    }



    // set hard coded values for category mappings
    const categoryMappings = {
        "L1-LCD Cosmetic Damage": { "code": "Cosmetics-16", "hierarchy": 1 },
        "05-Bezel Cosmetic Failure": { "code": "Cosmetic-5", "hierarchy": 2 },
        "Back Cover Cosmetic Failure": { "code": "Cosmetic-2", "hierarchy": 3 },
        "Power Button Cosmetic": { "code": "Cosmetic-23", "hierarchy": 20 },
        "L1-LCD Cracked": { "code": "Cosmetic-17", "hierarchy": 5 },
        "Silent Switch Cosmetic": { "code": "Cosmetic-27", "hierarchy": 34 },
        "Charging Port Wrong Color": { "code": "Cosmetic-13A", "hierarchy": 7 }
    };

    // Initial check to set the correct button visibility when the page loads
    toggleButtons();

    $("#applyFiltersButton").click(function() {
        fetchAndDisplayData(); // Now fetchAndDisplayData only gets called when this button is clicked.
    });


    // For Adding Threshold Rows
    $("#addThresholdRowButton").click(function() {
        $('#addRowModal').modal('show');
    });

    // For Adding Failure Reason Rows
    $("#addFailureReasonRowButton").click(function() {
        $('#addFailureReasonModal').modal('show');
    });

    
    // When adding a new row, clear previous selections 
    $("#addRowBelowButton, #addRowAboveButton").click(function() {
        var selectedUid = getSelectedRowUid();  // Get the UID of the selected row
        if (!selectedUid) return;

        var position = this.id === "addRowBelowButton" ? 'below' : 'above';
        var newData = {
            data_type: $("#data_type").val(),
            position: position,
            referenceUid: selectedUid,
            Grade: "New Grade",
            Surface: "New Surface",
            DefectType: "New Defect Type",
            Defect: "New Defect"
        };

        sendRowData(newData);
        //  clear selections after adding a new row
        $('.selected').removeClass('selected');
        selectedRows.clear();
        //fetchAndDisplayData();
        //refreshDisplay();
    });


    $("#deleteRowButton").click(function() {
        var selectedUids = getSelectedRowUids();  // Function to get UIDs of all selected rows
        if (selectedUids.length === 0) {
            alert("Please select one or more rows to delete.");
            return;
        }
    
        var confirmation = confirm("Are you sure you want to delete the selected row(s)?");
        if (!confirmation) {
            return; // Stop the deletion if the user does not confirm
        }
    
        var newData = {
            data_type: $("#data_type").val(),
            uids: selectedUids
        };
    
        $.ajax({
            url: '/delete_rows',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(newData),
            success: function(response) {
                alert(response.message);
                fetchAndDisplayData();  // Refresh the table display
            },
            error: function(xhr, status, error) {
                console.error("Error deleting row(s): ", status, error);
                alert("Error deleting row(s): " + error);
            }
        });
    });
    

    $("#submitGradeDetails").click(function() {
        console.log("Submit Grade Details button clicked");
        var grade = $("#gradeInput").val().trim() || 'NaN';  // Trim and check for empty string
        var surfaces = $("#surfaceInput").val() || ['NaN'];  // Default to ['NaN'] if empty
        var defectTypes = $("#defectTypeInput").val() || ['NaN'];  // Default to ['NaN'] if empty
        var defects = $("#defectInput").val();
        defects = defects && defects.length > 0 ? defects : ['NaN'];  // Explicitly handle the case where defects array is empty
    
        var rowsToAdd = [];
    
        surfaces.forEach(surface => {
            defectTypes.forEach(defectType => {
                defects.forEach(defect => {
                    var newRow = {
                        'data_type': $("#data_type").val(),
                        'Grade': grade,
                        'Surface': surface,
                        'Defect Type': defectType,
                        'Defect': defect
                    };
                    rowsToAdd.push(newRow);
                });
            });
        });
    
        console.log("Rows to Add (preparation): ", JSON.stringify(rowsToAdd, null, 2));
    
        if (rowsToAdd.length === 0 || (rowsToAdd.length === 1 && rowsToAdd[0].Defect === 'NaN' && rowsToAdd[0].Surface === 'NaN' && rowsToAdd[0]['Defect Type'] === 'NaN')) {
            console.log("No valid data to submit. Ensure at least one field is filled.");
            alert("No valid data to submit. Ensure at least one field is filled.");
            return; // Prevent submission if there's genuinely no data to submit.
        }
    
        // Proceed with AJAX request if there's data to submit
        $.ajax({
            url: '/add_row',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(rowsToAdd),
            success: function(response) {
                alert("Rows added successfully!");
                $('#addRowModal').modal('hide');
                $(".select2").val(null).trigger("change");  // Clear selections
                fetchAndDisplayData();  // Refresh data display
            },
            error: function(xhr, status, error) {
                console.error("Error adding rows: ", status, error);
                alert("Error adding rows. Please try again.");
            }
        });
    });

    $('#addRowModal').on('show.bs.modal', function (e) {
        // Clear existing options
        $("#surfaceInput").empty();
        $("#defectTypeInput").empty();
        $("#defectInput").empty();
    
        //  surfaces 
        var surfaces = ["A", "B", "C", "D", "L", "R", "T", "AA"];
        surfaces.forEach(function(surface) {
            $("#surfaceInput").append(new Option(surface, surface));
        });
    
        //  defect types 
        var defectTypes = ["major", "minor", "damaged", "level 1", "level 2", "deep scratch", "light scratch", ];
        defectTypes.forEach(function(type) {
            $("#defectTypeInput").append(new Option(type, type));
        });
    
        //  defects 
        var defects = ["dent", "nick", "scratch", "crack", "missingpart", "pindot", "grouppindot", "discoloration", "differentscreen"];
        defects.forEach(function(defect) {
            $("#defectInput").append(new Option(defect, defect));
        });
    
        // Initialize or re-initialize select2 for these fields
        $('.select2').select2({
            width: '100%',
            placeholder: "Select an option",
            allowClear: true,
            closeOnSelect: false
        });
    });



    $("#submitFailureReasonsDetails").click(function() {
        console.log("Submit Failure Reason Details button clicked");
        var grade = $("#gradesInput").val().trim() || 'NaN';  
        var category = $("#categoryInput").val();  //  single select
        // Ensure category is treated as a string, not an array
        category = Array.isArray(category) ? category[0] : category; // Take the first selected category if it's an array
        var defects = $("#defectsInput").val() || ['NaN'];  // Correctly ensure this is an array
        var surfaces = $("#surfacesInput").val() || ['NaN'];  // Ensure this is an array 
        var rowsToAdd = [];
        var code = categoryMappings[category] ? categoryMappings[category].code : 'NaN';
        var hierarchy = categoryMappings[category] ? categoryMappings[category].hierarchy : 'NaN';

        // Assuming you want to combine each category with defect and surface
        defects.forEach(defect => {
            surfaces.forEach(surface => {
                var newRow = {
                    'data_type': $("#data_type").val(),
                    'Grade': grade,
                    'Category': category,
                    'Code': code,
                    'Hierarchy': hierarchy,
                    'Defect': defect,
                    'Surface': surface,
                };
                rowsToAdd.push(newRow);
            });
        });
    
    
        console.log("Rows to Add (preparation): ", JSON.stringify(rowsToAdd, null, 2));

        if (rowsToAdd.length === 0 || rowsToAdd.some(row => row.Defect === 'NaN' || row.Surface === 'NaN')) {
            console.log("No valid data to submit. Ensure at least one field is filled.");
            alert("No valid data to submit. Ensure at least one field is filled.");
            return; // Prevent submission if there's genuinely no data to submit.
        }
    
        $.ajax({
            url: '/add_row',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(rowsToAdd),
            success: function(response) {
                alert("Rows added successfully!");
                $('#addFailureReasonModal').modal('hide');
                $(".select2").val(null).trigger("change");  // Clear selections
                fetchAndDisplayData();  // Refresh data display
            },
            error: function(xhr, status, error) {
                console.error("Error adding rows: ", status, error);
                alert("Error adding rows. Please try again.");
            }
        });
    });

    $('#addFailureReasonModal').on('show.bs.modal', function (e) {
        // Clear existing options
        $("#categoryInput").empty();
        $("#codeInput").empty();
        $("#hierarchyInput").empty();
        $("#defectsInput").empty();
        $("#surfacesInput").empty();

        //  categories 
        var categories = ["L1-LCD Cosmetic Damage", "05-Bezel Cosmetic Failure", "Back Cover Cosmetic Failure", "L1-LCD Cracked", "Power Button Cosmetic", "Silent Switch Cosmetic", "Charging Port Wrong Color"];
        categories.forEach(function(category) {
            $("#categoryInput").append(new Option(category, category));
        });

        //  codes 
        var codes = ["Cosmetics-16", "Cosmetic-5", "Cosmetic-2", "Cosmetic-17", "Cosmetic-23", "Cosmetic-27", "Cosmetic-13A"];
        codes.forEach(function(code) {
            $("#codeInput").append(new Option(code, code));
        });

        //  hierarchy 
        var hierarchy = ["1", "2", "3", "5", "20", "34", "7"];
        hierarchy.forEach(function(hier) {
            $("#hierarchyInput").append(new Option(hier, hier));
        });

        //  defect types 
        var defects = ["major", "minor", "damaged", "level 1", "level 2", "deep scratch", "light scratch", "discoloration" ];
        defects.forEach(function(defect) {
            $("#defectsInput").append(new Option(defect, defect));
        });
    
        //  surfaces 
        var surfaces = ["A", "B", "C", "D", "L", "R", "T", "AA"];
        surfaces.forEach(function(surface) {
            $("#surfacesInput").append(new Option(surface, surface));
        });
    
        // Initialize or re-initialize select2 for these fields
        $('.select2').select2({
            width: '100%',
            placeholder: "Select an option",
            allowClear: true,
            closeOnSelect: false
        });
    });

    // Event listener for data type change
    $('#data_type').change(function() {
        currentFilters = {}; // Reset filters when data type changes
        toggleButtons(); // Show/hide buttons based on the selected data type
        fetchAndDisplayData();
    });

    $('#filterOptions').on('change', 'select', function() {
        console.log($(this).val());
        let filterName = $(this).attr('id').replace('filter', '');
        let filterValues = $(this).val() || [];
    
        // Update currentFilters to handle an array of values
        if (filterValues.length > 0) {
            currentFilters[filterName] = filterValues;
        } else {
            delete currentFilters[filterName]; // Remove the filter if no option is selected
        }

    });

    // Initial fetch and display for the default data type ('Thresholds')
    fetchAndDisplayData({}); // No filters applied initially


    $(document).on('click', '#myTable tbody td', function() {
        let currentCell = $(this);
        let parentRow = currentCell.closest('tr');
    
        // Check if the parent row is selected before allowing editing
        if (!parentRow.hasClass('selected')) {
            alert("Please select this row first to edit.");
            return;  // Prevent editing if the row is not selected
        }
    
        if (!currentCell.find('input').length) {  // Only allow editing if there isn't already an input element
            let currentValue = currentCell.text();
            let inputField = $('<input>', {
                'value': currentValue,
                'type': 'text'
            }).addClass('form-control');
    
            currentCell.html(inputField);
            inputField.focus();
        }
    });


    // Collect updates when cells lose focus
    $(document).on('blur', '#myTable tbody input', function() {
        let inputField = $(this);
        let newValue = inputField.val();
        let cell = inputField.closest('td');
        let columnName = cell.attr('data-columnName');
        let dataType = $('#data_type').val();

        // Collect updates from all selected rows for this column
        Array.from(selectedRows).forEach(rowUid => {
            pendingUpdates.push({
                rowUid: rowUid,
                columnName: columnName,
                newValue: newValue,
                dataType: dataType
            });
        });

        // Reflect changes in the UI immediately for all selected rows
        $('#myTable tbody tr.selected td[data-columnName="' + columnName + '"]').text(newValue);
    });


    // Deselect rows and update data when clicking outside the table
    $(document).click(function(event) {
        if(!$(event.target).closest('#myTable').length && $('#myTable').is(":visible")) {
            batchUpdateData();  // Perform the pending batch update before clearing selections
            $('#myTable tbody tr.selected').removeClass('selected');
            selectedRows.clear();
        }
    });

    // Prevent the document click event from firing when clicking inside the table
    $('#myTable').click(function(event) {
        event.stopPropagation(); // Stop the click event from propagating to the document
    });

    

    // Export button functionality
    $('#exportButton').click(function() {
        window.location.href = '/export';

        //Delay the redirection to the home page to allow the download to initiate
        setTimeout(function() {
            window.location.href = '/';
        }, 2000);

    });
    
    
});
