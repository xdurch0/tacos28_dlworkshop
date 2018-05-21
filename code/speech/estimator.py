import argparse

import tensorflow as tf

from data import input_fn


N_CLASSES = 30


def model_fn_linear(features, labels, mode, params):
    base_lr = params["base_lr"]
    end_lr = params["end_lr"]
    decay_steps = params["decay_steps"]
    decay_power = params["decay_power"]
    reg_type = params["reg_type"]
    reg_coeff = params["reg_coeff"]
    if reg_type == "l1":
        reg = lambda x: tf.norm(x, ord=1)
    elif reg_type == "l2":
        reg = lambda x: tf.norm(x, ord=2)
    else:
        reg = None

    logits = tf.layers.dense(features, N_CLASSES, kernel_regularizer=reg)

    if mode == tf.estimator.ModeKeys.PREDICT:
        predictions = {"logits": logits,
                       "probabilities": tf.nn.softmax(logits),
                       "input": features}
        return tf.estimator.EstimatorSpec(mode=mode, predictions=predictions)

    cross_ent = tf.losses.sparse_softmax_cross_entropy(
        labels=labels, logits=logits)
    tf.summary.scalar("cross_ent", cross_ent)
    loss = cross_ent
    reg_loss = tf.losses.get_regularization_loss()
    tf.summary.scalar("reg_loss", reg_loss)
    if reg_coeff:
        loss += reg_coeff * reg_loss

    acc = tf.reduce_mean(
        tf.cast(tf.equal(tf.argmax(logits, axis=1, output_type=tf.int32), labels),
                tf.float32))
    tf.summary.scalar("accuracy", acc)

    if mode == tf.estimator.ModeKeys.TRAIN:
        gs = tf.train.get_global_step()
        lr = tf.train.polynomial_decay(base_lr, gs, decay_steps, end_lr,
                                       decay_power)
        tf.summary.scalar("learing_rate", lr)
        train_op = tf.train.AdamOptimizer(lr).minimize(loss,
                                                       global_step=gs)
        return tf.estimator.EstimatorSpec(mode=mode, loss=cross_ent,
                                          train_op=train_op)

    eval_metric_ops = {"accuracy": tf.metrics.accuracy(labels, logits),
                       "cross_ent": tf.metrics.mean(cross_ent)}
    return tf.estimator.EstimatorSpec(mode=mode, loss=cross_ent,
                                      eval_metric_ops=eval_metric_ops)


parser = argparse.ArgumentParser()
parser.add_argument("mode")
parser.add_argument("base_path")
parser.add_argument("model_dir")
parser.add_argument("-B", "--batch_size",
                    type=int,
                    default=128)
parser.add_argument("-L", "--learning_rate",
                    nargs=2,
                    type=float,
                    default=[0.001, 0.0000001],
                    help="Initial/final learning rate.")
parser.add_argument("-D", "--decay",
                    nargs=2,
                    type=float,
                    default=[100000, 2.0],
                    help="Decay steps and power.")
parser.add_argument("-R", "--reg",
                    nargs=2,
                    default=[None, 0.0],
                    help="Regularization type and coefficient.")
args = parser.parse_args()

prms = {"base_lr": args.learning_rate[0],
        "end_lr": args.learning_rate[1],
        "decay_steps": int(args.decay[0]),
        "decay_power": args.decay[1],
        "reg_type": args.reg[0],
        "reg_coeff": float(args.reg[1])}

tf.logging.set_verbosity(tf.logging.INFO)

est = tf.estimator.Estimator(model_fn=model_fn_linear,
                             model_dir=args.model_dir,
                             params=prms)

if args.mode == "train":
    est.train(input_fn=lambda: input_fn(args.base_path, "train", args.batch_size),
              steps=int(args.decay[0]))
elif args.mode == "predict":
    preds = est.predict(input_fn=lambda: input_fn(args.base_path, "dev", args.batch_size))
elif args.mode == "eval":
    print(est.evaluate(input_fn=lambda: input_fn(args.base_path, "dev", args.batch_size)))
