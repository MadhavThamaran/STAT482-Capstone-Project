
# elastic_net_models.R

library(tidyverse)
library(glmnet)

final_df <- read.csv("final_df(elasticnet).csv")

# check columns
colnames(final_df)
str(final_df)

# clean for modeling
model_df <- final_df %>%
  mutate(
    domestic_gross = as.numeric(domestic_gross),
    averageRating = as.numeric(averageRating),
    runtimeMinutes = as.numeric(runtimeMinutes),
    startYear = as.numeric(startYear),
    numVotes = as.numeric(numVotes),
    is_book = as.numeric(is_book),
    log_domestic_gross = log(domestic_gross),
    log_numVotes = log(numVotes),
    decade = floor(startYear / 10) * 10,
    genres = sub(",.*", "", genres)
  ) %>%
  select(
    averageRating,
    log_domestic_gross,
    runtimeMinutes,
    genres,
    decade,
    log_numVotes,
    is_book
  ) %>%
  drop_na()

# split data
set.seed(482)
train_index <- sample(seq_len(nrow(model_df)), size = 0.8 * nrow(model_df))
train_data <- model_df[train_index, ]
test_data  <- model_df[-train_index, ]


# elastic net for imdb

# create model matrix on full dataset first
x_imdb <- model.matrix(
  averageRating ~ runtimeMinutes + genres + decade + log_numVotes + is_book,
  data = model_df
)[, -1]
y_imdb <- model_df$averageRating

# split after matrix is created
train_index <- sample(seq_len(nrow(model_df)), size = 0.8 * nrow(model_df))

x_train_imdb <- x_imdb[train_index, ]
x_test_imdb  <- x_imdb[-train_index, ]
y_train_imdb <- y_imdb[train_index]
y_test_imdb  <- y_imdb[-train_index]



cv_imdb <- cv.glmnet(
  x_train_imdb,
  y_train_imdb,
  alpha = 0.5,
  nfolds = 10,
  family = "gaussian"
)

print(coef(cv_imdb, s = "lambda.min"))

pred_imdb <- predict(cv_imdb, s = "lambda.min", newx = x_test_imdb)

x_gross <- model.matrix(
  log_domestic_gross ~ runtimeMinutes + genres + decade + log_numVotes + is_book,
  data = model_df
)[, -1]

y_gross <- model_df$log_domestic_gross

x_train_gross <- x_gross[train_index, ]
x_test_gross  <- x_gross[-train_index, ]

y_train_gross <- y_gross[train_index]
y_test_gross  <- y_gross[-train_index]

cv_gross <- cv.glmnet(
  x_train_gross,
  y_train_gross,
  alpha = 0.5,
  nfolds = 10,
  family = "gaussian"
)

print(coef(cv_gross, s = "lambda.min"))
pred_gross <- predict(cv_gross, s = "lambda.min", newx = x_test_gross)



# cross-validation plot
# error vs lambda
# best lambda selected
plot(cv_imdb)
title("Elastic Net Cross-Validation (IMDb Rating)")



# coefficient path plot
# which variables stay important
plot(cv_imdb$glmnet.fit, xvar = "lambda", label = TRUE)
title("Coefficient Paths (IMDb Model)")



# predicted vs actual plot
plot(y_test_imdb, pred_imdb,
     xlab = "Actual IMDb Rating",
     ylab = "Predicted IMDb Rating",
     main = "Predicted vs Actual IMDb Ratings")
abline(0, 1, lty = 2)


# same plots for gross
plot(cv_gross)
plot(cv_gross$glmnet.fit, xvar = "lambda", label = TRUE)

plot(y_test_gross, pred_gross,
     xlab = "Actual Log Gross",
     ylab = "Predicted Log Gross",
     main = "Predicted vs Actual Gross")
abline(0, 1, lty = 2)

