import json
import os
import boto3
from openai import OpenAI
from botocore.exceptions import ClientError

# Initialize clients
s3_client = boto3.client('s3')
openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

def parse_s3_url(s3_url):
    """
    Parse S3 URL to extract bucket and key.
    Supports formats:
    - s3://bucket-name/key
    - https://bucket-name.s3.region.amazonaws.com/key
    - https://s3.region.amazonaws.com/bucket-name/key
    """
    if s3_url.startswith('s3://'):
        parts = s3_url[5:].split('/', 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ''
        return bucket, key
    elif 'amazonaws.com' in s3_url:
        # Handle HTTPS S3 URLs
        if '.s3.' in s3_url or '.s3-' in s3_url:
            # Format: https://bucket.s3.region.amazonaws.com/key
            parts = s3_url.split('.s3')
            bucket = parts[0].replace('https://', '')
            key_part = s3_url.split('.amazonaws.com/', 1)
            key = key_part[1] if len(key_part) > 1 else ''
            return bucket, key
        elif 's3.amazonaws.com' in s3_url or 's3.' in s3_url:
            # Format: https://s3.region.amazonaws.com/bucket/key
            path_part = s3_url.split('.amazonaws.com/', 1)[1]
            parts = path_part.split('/', 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ''
            return bucket, key
    
    raise ValueError(f"Invalid S3 URL format: {s3_url}")

def get_presigned_url(bucket, key, expiration=3600):
    """
    Generate a presigned URL for the S3 object.
    This allows OpenAI to access the image temporarily.
    """
    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except ClientError as e:
        raise Exception(f"Error generating presigned URL: {str(e)}")

def analyze_sports_card(image_url):
    """
    Use OpenAI Vision API to analyze the sports card image.
    """
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # or "gpt-4-turbo" or "gpt-4o-mini" for cost savings
            messages=[
                {
                    "role": "system",
                    "content": """
                        Analyze the provided sports card image and extract detailed information. 
                        Return a JSON object with the following fields:
                        - player_name: Full name of the player
                        - sport: Type of sport (Choose from: Baseball, Basketball, Football, Hockey, Soccer)
                        - year: Year the card was produced
                        - brand: Card manufacturer/brand (Choose from: Topps, Panini, Upper Deck)
                        - card_number: Card number if visible. If not visible, return null.
                        - set_name: Name of the card set/series (e.g., Rated Rookie, Select, Optic, Mosaic, etc.)
                        - team: Team name
                        - card_parallel: Type of card (e.g., Prizm, Gold, Green, Blue Prizm, Cracked Ice, etc.)
                        - rookie: Whether the card is a rookie card. If not visible, return null.
                        - special_features: Array of special features (e.g., autograph, jersey piece)
                        - grade: Grade of the card. If not visible, return null.
                        - grader: Name of the grader. If not visible, return null.
                        - confidence: Your confidence level in the analysis (0-100)
                        
                        If any field cannot be determined, use null. If fields like set_name or car_parallel can be 
                        provided using previous knowledge, use that knowledge to provide the best answer. Be as accurate as possible.
                    """.strip()
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Please analyze this sports card image and provide detailed information in JSON format."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url,
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=1000,
            temperature=0.1  # Lower temperature for more consistent results
        )
        
        # Extract the response content
        content = response.choices[0].message.content
        
        # Try to parse as JSON
        try:
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()
            
            card_details = json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, return the raw content
            card_details = {
                "raw_response": content,
                "error": "Failed to parse as JSON"
            }
        
        return card_details
        
    except Exception as e:
        raise Exception(f"Error analyzing image with OpenAI: {str(e)}")

def main(event, context):
    """
    Lambda function handler.
    
    Expected event format:
    {
        "s3_url": "s3://bucket-name/path/to/image.jpg"
    }
    OR
    {
        "bucket": "bucket-name",
        "key": "path/to/image.jpg"
    }
    """
    try:
        # Extract S3 information from event
        if 's3_url' in event:
            s3_url = event['s3_url']
            bucket, key = parse_s3_url(s3_url)
        elif 'bucket' in event and 'key' in event:
            bucket = event['bucket']
            key = event['key']
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'Missing required parameters. Provide either "s3_url" or both "bucket" and "key".'
                })
            }
        
        # Generate presigned URL for OpenAI to access the image
        presigned_url = get_presigned_url(bucket, key)
        
        # Analyze the card using OpenAI
        card_details = analyze_sports_card(presigned_url)
        
        # Return successful response
        response = {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'  # Enable CORS
            },
            'body': json.dumps({
                'success': True,
                'card_details': card_details,
                's3_location': {
                    'bucket': bucket,
                    'key': key
                }
            })
        }
        print(f"Response: {response}")
        return response
        
    except ValueError as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 400,
            'body': json.dumps({
                'error': f'Invalid input: {str(e)}'
            })
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }

if __name__ == "__main__":
    main({"s3_url": "s3://cardx-application/cards/images/e6537498-d3cd-4ede-9b34-b64dd0f5146d.jpeg"}, {})