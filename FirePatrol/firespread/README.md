Wildfire Spread Prediction System

This document describes the file structure, components, and responsibilities of a wildfire spread prediction system built using satellite terrain data, weather APIs, and a machine learning model trained on FireBench simulations.

📂 Directory Structure

firespread/

|-- fire_model.h5                                             # Trained Keras model (HDF5 format)

|-- firebench_dataset.csv         # Training dataset extracted from FireBench

|-- fire_predictor.py             # Prediction script using the trained model

|-- model_trainer.py              # Training and evaluation logic

|-- train_from_csv.py             # CSV-based model training runner

|-- firebench_loader.py           # FireBench Zarr loader and preprocessor

|-- gps_utils.py                  # Pixel-to-GPS coordinate converter

|-- terrain_reader.py             # Extract slope from GeoTIFF using lat/lon

|-- weather_api.py                # Weather API integration for wind data

|-- Slope_All.tif                 # GeoTIFF file of slope (entire Korea)

|-- Slope_All.tfw                 # World file with affine transformation metadata

🔍 Component Descriptions

1. fire_model.h5

Format: Keras HDF5 model

Purpose: Final model that predicts wildfire spread direction and speed.

Input: [wind_dir, wind_speed, slope_deg, slope_dir, alignment]

Output: [spread_dir, spread_speed]

2. firebench_dataset.csv

Contents: Preprocessed data for training

Columns:

Features: wind_dir, wind_speed, slope_deg, slope_dir

Targets: spread_dir, spread_speed

3. fire_predictor.py

Loads the fire_model.h5 model.

Provides predict_fire_spread() function for real-time inference.

Adds engineered feature: relative_alignment = cos(wind_dir - slope_dir).

4. model_trainer.py

Adds engineered features to training data.

Trains MultiOutputRegressor(RandomForestRegressor).

Saves model to .pkl or .h5.

Provides MAE and RMSE evaluation functions.

5. train_from_csv.py

Loads firebench_dataset.csv or triggers dataset generation if absent.

Calls training and evaluation routines.

Saves model to file.

6. firebench_loader.py

Loads FireBench .zarr files from GCS bucket (public read).

Extracts wind vectors and fire spread statistics.

Infers slope angle and direction from file paths.

Builds and saves training samples.

7. gps_utils.py

Provides pixel_to_gps():

Uses CCTV field-of-view and azimuth

Converts pixel location to geographic coordinates

Based on geodesic forward projection

8. weather_api.py

Calls Korea Meteorological Administration (KMA) API.

Transforms lat/lon to KMA grid coordinates.

Retrieves wind components: UUU, VVV, WSD.

Computes wind direction and speed.

9. terrain_reader.py

Reads GeoTIFF slope data (Slope_All.tif).

Transforms WGS84 lat/lon to raster coordinates.

Returns slope at specified pixel location.

10. Slope_All.tif

Nationwide slope raster file.

Single band: slope angle in degrees.

Used for real-time slope feature extraction.

11. Slope_All.tfw

Associated world file for Slope_All.tif.

Contains affine transform parameters.

Ensures spatial alignment with lat/lon queries.

🌀 End-to-End Workflow Summary

Input: CCTV metadata (location, azimuth, FOV) + pixel location.

GPS Estimation: pixel_to_gps() computes geographic coordinates.

Wind Retrieval: get_wind_data() queries KMA API.

Slope Extraction: get_slope_from_geotiff() samples GeoTIFF.

Model Prediction: predict_fire_spread() returns direction/speed.

🚫 Limitations

FireBench simulation data may not generalize well to real terrain.

Terrain slope inference is resolution-limited by the GeoTIFF.

KMA API rate-limiting or downtime may affect real-time inference.

📖 References

FireBench Dataset (Google Cloud Storage, v2024.04)

Korea Meteorological Administration (https://www.data.go.kr)

RasterIO, pyproj, scikit-learn, TensorFlow/Keras

