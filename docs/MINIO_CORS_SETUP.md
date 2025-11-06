# MinIO CORS Configuration

## Overview

MinIO requires explicit CORS (Cross-Origin Resource Sharing) configuration to allow browsers to upload files directly to presigned URLs. Without proper CORS configuration, browsers will block PUT requests with a CORS error.

## Problem

When the frontend attempts to upload files via presigned URLs to MinIO, the browser enforces CORS policy. If MinIO is not configured to accept cross-origin requests from the frontend origin, uploads fail with:

```
CORS error: Access to XMLHttpRequest at '...' from origin 'http://localhost:3000'
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
on the requested resource.
```

## Solution

### For Development (Docker)

#### Using MinIO's Admin API

1. Access the MinIO Admin Console or use the `mc` (MinIO Client):

```bash
# Set alias for your MinIO instance
mc alias set myminio http://localhost:9000 minioadmin minioadmin123

# Set CORS policy for the legal-documents bucket
mc cors set myminio/legal-documents --set '
{
  "CORSRules": [
    {
      "AllowedOrigins": [
        "http://localhost:3000",
        "http://localhost:5001"
      ],
      "AllowedMethods": [
        "GET",
        "PUT",
        "POST",
        "DELETE",
        "HEAD"
      ],
      "AllowedHeaders": [
        "*"
      ],
      "ExposeHeaders": [
        "ETag",
        "x-amz-meta-*"
      ],
      "MaxAgeSeconds": 3600
    }
  ]
}
'
```

#### Using Python boto3 SDK

```python
import boto3
from minio import Minio
import json

client = Minio(
    'localhost:9000',
    access_key='minioadmin',
    secret_key='minioadmin123',
    secure=False
)

# Define CORS configuration
cors_config = {
    "CORSRules": [
        {
            "AllowedOrigins": ["http://localhost:3000", "http://localhost:5001"],
            "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["ETag", "x-amz-meta-*"],
            "MaxAgeSeconds": 3600
        }
    ]
}

# Apply CORS policy
client.set_bucket_cors("legal-documents", cors_config)
```

#### Using AWS CLI (S3-compatible)

```bash
aws --endpoint-url http://localhost:9000 \
  s3api put-bucket-cors \
  --bucket legal-documents \
  --cors-configuration '{
    "CORSRules": [
      {
        "AllowedOrigins": ["http://localhost:3000", "http://localhost:5001"],
        "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
        "AllowedHeaders": ["*"],
        "ExposeHeaders": ["ETag", "x-amz-meta-*"],
        "MaxAgeSeconds": 3600
      }
    ]
  }'
```

### For Production

For production deployments:

1. **Use HTTPS**: Ensure both MinIO and frontend use HTTPS
2. **Restrict Origins**: Use specific origin URLs instead of wildcard
   ```json
   "AllowedOrigins": ["https://yourdomain.com", "https://app.yourdomain.com"]
   ```

3. **Limit Methods**: Only allow methods your application uses
   - Use only PUT for uploads
   - Use only GET for downloads
   - Avoid allowing DELETE unless necessary

4. **Restrict Headers**: Instead of `"*"`, specify headers your frontend sends:
   ```json
   "AllowedHeaders": ["Content-Type", "x-amz-*"]
   ```

5. **Set Lower MaxAgeSeconds**: Consider reducing from 3600 to 600 seconds

## Testing CORS Configuration

### Using curl

```bash
# Test preflight request (OPTIONS)
curl -i -X OPTIONS \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: PUT" \
  -H "Access-Control-Request-Headers: content-type" \
  http://localhost:9000/legal-documents/
```

### Expected Response Headers

```
HTTP/1.1 200 OK
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET,PUT,POST,DELETE,HEAD
Access-Control-Allow-Headers: *
Access-Control-Max-Age: 3600
```

### Using Browser Console

```javascript
// Test from browser console to verify CORS headers
fetch('http://localhost:9000/legal-documents/', {
  method: 'OPTIONS',
  headers: {
    'Origin': window.location.origin,
    'Access-Control-Request-Method': 'PUT',
    'Access-Control-Request-Headers': 'content-type'
  }
}).then(r => {
  console.log('CORS Headers:', {
    'Access-Control-Allow-Origin': r.headers.get('Access-Control-Allow-Origin'),
    'Access-Control-Allow-Methods': r.headers.get('Access-Control-Allow-Methods'),
    'Access-Control-Allow-Headers': r.headers.get('Access-Control-Allow-Headers')
  });
});
```

## Troubleshooting

### Issue: "CORS policy: No Access-Control-Allow-Origin header"

**Solution:**
1. Verify CORS is configured: `mc cors get myminio/legal-documents`
2. Ensure origin in CORS rules matches frontend origin exactly (case-sensitive)
3. Check that the bucket exists and is accessible

### Issue: "CORS policy: Credential mode is 'include' but Access-Control-Allow-Credentials is missing"

**Solution:**
Add `"AllowCredentials": true` to CORS rules and include credentials in fetch:

```javascript
fetch(uploadUrl, {
  method: 'PUT',
  body: file,
  credentials: 'include',
  headers: {...}
})
```

Then update CORS:
```json
"AllowCredentials": true,
"AllowedOrigins": ["http://localhost:3000"]  // Cannot use * with credentials
```

### Issue: Presigned URLs are being blocked

**Solution:**
1. Ensure frontend is accessing MinIO via the same hostname as the presigned URL
2. Verify the presigned URL is using the public endpoint (`MINIO_PUBLIC_ENDPOINT`)
3. Check that URL expiration hasn't passed

## References

- [MinIO CORS Documentation](https://docs.min.io/minio/baremetal/security/server-side-encryption/data-access-levels.html)
- [AWS S3 CORS Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/cors.html)
- [MDN CORS Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
