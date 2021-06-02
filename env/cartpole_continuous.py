"""
Classic cart-pole system with continuous action implemented by Rich Sutton et al.
Copied from http://incompleteideas.net/sutton/book/code/pole.c
permalink: https://perma.cc/C9ZM-652R
"""

import logging
import gym
from gym import spaces
from gym.utils import seeding
import autograd.numpy as np

logger = logging.getLogger(__name__)

class CartPoleContinuousEnv(gym.Env):
    metadata = {
        'render.modes': ['human', 'rgb_array'],
        'video.frames_per_second' : 200
    }

    def __init__(self):
        self.gravity = 9.8
        self.masscart = 0.5
        self.masspole = 0.1
        self.total_mass = (self.masspole + self.masscart)
        self.length = 0.3 # actually half the pole's length
        self.polemass_length = (self.masspole * self.length)
        self.max_force = 20.0
        self.tau = 0.005  # seconds between state updates
        self.b = 0.1
        self.I = 0.012
        G = np.loadtxt('G.txt')
        H = np.loadtxt('H.txt').reshape(4, 1)
        self.F_t = np.concatenate([G, H], axis=1)

        # Angle at which to fail the episode
        self.theta_threshold_radians = 12 * 2 * np.pi / 360
        self.x_threshold = 2.4

        # Angle limit set to 2 * theta_threshold_radians so failing observation is still within bounds
        high = np.array([
            self.x_threshold * 2,
            np.finfo(np.float32).max,
            self.theta_threshold_radians * 2,
            np.finfo(np.float32).max])

        self.action_space = spaces.Box(low=-self.max_force, high=self.max_force, shape=(1,))
        self.observation_space = spaces.Box(-high, high)

        self._seed()
        self.viewer = None
        self.state = None

        self.steps_beyond_done = None

    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def _state_eq(self, st, u):
        states = np.concatenate([st, u]).T
        result = self.F_t@states.ravel()
        # print("result", result)
        # return result
        x, x_dot, theta, theta_dot = st

        pre_theta = theta

        force = -u[0]
        costheta = np.cos(theta)
        sintheta = np.sin(theta)
        temp = (force + self.polemass_length * theta_dot * theta_dot * sintheta - self.b*x_dot) / self.total_mass
        
        thetaacc = (self.gravity * sintheta - costheta* temp) / (self.I/(self.masspole) + self.length - self.masspole * costheta**2 / self.total_mass)
        xacc  = temp - self.polemass_length * thetaacc * costheta / self.total_mass
        
        x  = x + self.tau * x_dot
        x_dot = x_dot + self.tau * xacc
        theta = theta + self.tau * theta_dot
        theta_dot = theta_dot + self.tau * thetaacc

        if pre_theta < np.pi and theta >= np.pi:
            theta -= 2*np.pi 
        elif pre_theta > -np.pi and theta <= -np.pi:
            theta += 2*np.pi

        return np.array([x, x_dot, theta, theta_dot])

    def _step(self, action):
        # assert self.action_space.contains(action), "%r (%s) invalid"%(action, type(action))
        state = self.state
        self.state = self._state_eq(state, action)
        # print("true state", self.state) 
        x, x_dot, theta, theta_dot = self.state
        done =  x < -self.x_threshold \
                or x > self.x_threshold \
                or theta < -self.theta_threshold_radians \
                or theta > self.theta_threshold_radians
        done = bool(done)

        if not done:
            reward = 1.0
        elif self.steps_beyond_done is None:
            # Pole just fell!
            self.steps_beyond_done = 0
            reward = 1.0
        else:
            if self.steps_beyond_done == 0:
                logger.warning("You are calling 'step()' even though this environment has already returned done = True. You should always call 'reset()' once you receive 'done = True' -- any further steps are undefined behavior.")
            self.steps_beyond_done += 1
            reward = 0.0

        return self.state, reward, done, {}

    def _reset(self):
        self.state = np.array([-5.0, 0.0, 0.3 * np.pi, 0.0])
        self.steps_beyond_done = None
        return np.array(self.state)

    def _render(self, mode='human', close=False):
        if close:
            if self.viewer is not None:
                self.viewer.close()
                self.viewer = None
            return

        screen_width = 1200
        screen_height = 400

        world_width = self.x_threshold*2
        scale = screen_width/world_width/3
        carty = 100 # TOP OF CART
        polewidth = 10.0
        polelen = scale * 1.0
        cartwidth = 50.0
        cartheight = 30.0

        if self.viewer is None:
            from gym.envs.classic_control import rendering
            self.viewer = rendering.Viewer(screen_width, screen_height)
            l,r,t,b = -cartwidth/2, cartwidth/2, cartheight/2, -cartheight/2
            axleoffset =cartheight/4.0
            cart = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
            self.carttrans = rendering.Transform()
            cart.add_attr(self.carttrans)
            self.viewer.add_geom(cart)
            l,r,t,b = -polewidth/2,polewidth/2,polelen-polewidth/2,-polewidth/2
            pole = rendering.FilledPolygon([(l,b), (l,t), (r,t), (r,b)])
            pole.set_color(.8,.6,.4)
            self.poletrans = rendering.Transform(translation=(0, axleoffset))
            pole.add_attr(self.poletrans)
            pole.add_attr(self.carttrans)
            self.viewer.add_geom(pole)
            self.axle = rendering.make_circle(polewidth/2)
            self.axle.add_attr(self.poletrans)
            self.axle.add_attr(self.carttrans)
            self.axle.set_color(.5,.5,.8)
            self.viewer.add_geom(self.axle)
            self.track = rendering.Line((0,carty), (screen_width,carty))
            self.track.set_color(0,0,0)
            self.viewer.add_geom(self.track)

        if self.state is None: return None

        x = self.state
        cartx = x[0]*scale+screen_width/2.0 # MIDDLE OF CART
        self.carttrans.set_translation(cartx, carty)
        self.poletrans.set_rotation(-x[2])

        return self.viewer.render(return_rgb_array = mode=='rgb_array')
