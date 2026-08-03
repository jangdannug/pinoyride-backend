aws ecr get-login-password --region ap-southeast-1 \
  | docker login --username AWS --password-stdin \
  542784561613.dkr.ecr.ap-southeast-1.amazonaws.com

docker buildx build \
  --platform linux/arm64 \
  -t 542784561613.dkr.ecr.ap-southeast-1.amazonaws.com/pinoyride-backend-production:latest \
  --push .