FROM public.ecr.aws/lambda/python:3.11

# Copy function code
COPY . .

# Install the function's dependencies using file requirements.txt
RUN pip install --editable .
RUN pip3 install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Set the CMD to <script_name>.lambda_handler using the AWS console