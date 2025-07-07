# Twitter API Test Suite

This directory contains comprehensive tests for the Twitter API integration used in the silicon_echo workflow.

## Test Files

### 1. `test_text_only.py`
- **Purpose**: Tests posting text-only tweets
- **Requirements**: No additional files needed
- **What it tests**: Basic tweet posting functionality

### 2. `test_text_media.py`
- **Purpose**: Tests posting tweets with images
- **Requirements**: Add image files (.jpg, .jpeg, .png, .gif) to this directory
- **What it tests**: Media upload and tweet posting with media

### 3. `test_media_only.py`
- **Purpose**: Tests posting tweets with only media (no text)
- **Requirements**: Add image files (.jpg, .jpeg, .png, .gif) to this directory
- **What it tests**: Media-only tweet posting

### 4. `test_text_video.py`
- **Purpose**: Tests posting tweets with videos
- **Requirements**: Add video files (.mp4, .mov, .avi, .m4v) to this directory
- **What it tests**: Video upload, processing, and tweet posting with video

### 5. `run_all_tests.py`
- **Purpose**: Runs all tests in sequence
- **Requirements**: All test files and media files for media/video tests
- **What it does**: Executes all tests and provides a summary report

## Setup

1. **Environment Variables**: Ensure your `.env` file in `workflows/silicon_echo/` contains all required Twitter API credentials:
   ```
   TWITTER_API_KEY=your_api_key
   TWITTER_API_SECRET_KEY=your_api_secret_key
   TWITTER_ACCESS_TOKEN=your_access_token
   TWITTER_ACCESS_TOKEN_SECRET=your_access_token_secret
   TWITTER_BEARER_TOKEN=your_bearer_token
   ```

2. **App Permissions**: Make sure your Twitter app has "Read and write and Direct message" permissions

3. **Test Media**: Add test files to this directory:
   - **Images**: `.jpg`, `.jpeg`, `.png`, `.gif` files for image tests
   - **Videos**: `.mp4`, `.mov`, `.avi`, `.m4v` files for video tests

## Running Tests

### Run All Tests
```bash
cd tests/twitter
python run_all_tests.py
```

### Run Individual Tests
```bash
cd tests/twitter

# Text-only tweet
python test_text_only.py

# Text + media tweet (requires image files)
python test_text_media.py

# Media-only tweet (requires image files)
python test_media_only.py

# Text + video tweet (requires video files)
python test_text_video.py
```

## Test Requirements

### Image Requirements
- **Formats**: JPG, JPEG, PNG, GIF
- **Size**: Maximum 5MB per image
- **Quantity**: Up to 4 images per tweet

### Video Requirements
- **Formats**: MP4, MOV, AVI, M4V
- **Size**: Maximum 512MB
- **Duration**: Maximum 2 minutes 20 seconds
- **Processing**: Videos require processing time (up to 5 minutes)

## Troubleshooting

### Common Issues

1. **403 Forbidden Errors**
   - Regenerate your Twitter API tokens after changing app permissions
   - Ensure app has "Read and write and Direct message" permissions

2. **401 Unauthorized Errors**
   - Check your API credentials in the `.env` file
   - Verify tokens are regenerated after permission changes

3. **Media Upload Failures**
   - Check file size and format requirements
   - Ensure files are not corrupted
   - For videos, wait for processing to complete

4. **Duplicate Content Errors**
   - Tests include timestamps to avoid duplicates
   - If you get duplicate errors, wait a few minutes between test runs

### Debug Mode

Each test provides detailed logging including:
- Authentication status
- File information (size, type)
- Upload progress
- Error details with tracebacks

## Test Results

The test suite will provide:
- ✅ **PASSED**: Test completed successfully
- ❌ **FAILED**: Test failed (check error messages)
- ⏰ **TIMEOUT**: Test took too long (5-minute limit)
- 💥 **ERROR**: Unexpected error occurred

## Integration with silicon_echo

These tests use the same authentication setup as the main `silicon_echo.py` workflow:
- Same `.env` file location
- Same API client configuration
- Same error handling patterns

This ensures that if the tests pass, the main workflow should work correctly. 