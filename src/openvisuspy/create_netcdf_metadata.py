import netCDF4 as nc

def create_netcdf_metadata(existing_nc, new_nc, idx_url):
    """
    Copies metadata, dimensions, and variables from an existing netCDF file to a new netCDF file
    and adds a custom idx url attribute.

    Parameters:
    existing_nc (str): The path to the existing netCDF file with all data/metadata from which to copy.
    new_nc (str): The path to the new netCDF file to be created.
    idx_url (str): The IDX URL to add as a global attribute to the new netCDF file.

    Returns:
    None: This function does not return any value but creates a new netCDF file with modified contents.
    """
    existing_dataset = nc.Dataset(existing_nc)
    new_dataset = nc.Dataset(new_nc, 'w', format='NETCDF4')

    for dimname, dim in existing_dataset.dimensions.items():
        new_dataset.createDimension(dimname, len(dim) if not dim.isunlimited() else None)

    for varname, var in existing_dataset.variables.items():
        new_var = new_dataset.createVariable(varname, var.dtype, var.dimensions)
        new_var.setncatts({k: var.getncattr(k) for k in var.ncattrs()})
        
        # If a variable is one-dimensional and its name matches its dimension, copy its data.
        if len(var.dimensions) == 1:
            new_var[:] = var[:] 

    for attname in existing_dataset.ncattrs():
        new_dataset.setncattr(attname, existing_dataset.getncattr(attname))

    # Adding a new idx_url attribute
    attribute_name = 'idx_url'
    attribute_value = idx_url
    new_dataset.setncattr(attribute_name, attribute_value)

    existing_dataset.close()
    new_dataset.close()
